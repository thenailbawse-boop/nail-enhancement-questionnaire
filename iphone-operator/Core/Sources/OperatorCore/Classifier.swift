import Foundation

/// Words the classifier treats as "creator content" or "personal memory" signals.
/// The founder can change the creator words in the app (Home → Advanced) to fit the
/// friend's niche. Matching is on Apple Vision label names (e.g. "food", "cosmetics").
struct ClassifierConfig: Codable, Hashable, Sendable {
    var creatorKeywords: Set<String>
    var personalKeywords: Set<String>
    /// A label must be at least this confident to count.
    var minimumLabelConfidence: Double = 0.30
    /// The winning signal must reach this to avoid "Needs Review".
    var decisionThreshold: Double = 0.50

    static let defaultCreatorKeywords: Set<String> = [
        "nail", "fingernail", "manicure", "nail_polish", "cosmetics", "makeup", "lipstick",
        "jewelry", "ring", "bracelet", "necklace", "fashion", "clothing", "dress", "shoes",
        "handbag", "food", "dessert", "cake", "drink", "coffee", "cocktail", "flower",
        "bouquet", "interior_room", "studio", "product", "packaging", "fitness", "gym"
    ]

    static let defaultPersonalKeywords: Set<String> = [
        "people", "adult", "child", "baby", "teen", "crowd", "dog", "cat", "pet", "animal",
        "wedding", "birthday", "celebration", "party", "beach", "mountain", "sky", "sunset",
        "landscape", "family", "graduation", "christmas_tree", "holiday"
    ]

    static let standard = ClassifierConfig(
        creatorKeywords: defaultCreatorKeywords,
        personalKeywords: defaultPersonalKeywords
    )

    /// Parses a comma separated list like "nail, cosmetics , Food" into normalized keys.
    static func parseKeywords(_ text: String) -> Set<String> {
        Set(text.split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased().replacingOccurrences(of: " ", with: "_") }
            .filter { !$0.isEmpty })
    }
}

/// Deterministic, explainable rules. Same input → same answer. Uncertain → Needs Review.
/// This is the fallback "brain" that works on every iPhone, with or without Apple Intelligence.
enum MediaClassifier {
    static func classify(_ facts: MediaFacts, config: ClassifierConfig = .standard) -> ClassificationDecision {
        if facts.isScreenshot {
            return ClassificationDecision(category: .screenshots, confidence: 1.0,
                                          reason: "iPhone marked this as a screenshot.")
        }

        if facts.kind == .video {
            var reason = "Video (\(formatDuration(facts.duration)))."
            if facts.isVertical && facts.duration >= 3 && facts.duration <= 180 {
                reason += " Tall and short — could be a Reel draft."
            }
            reason += " Video contents were not analyzed."
            return ClassificationDecision(category: .videos, confidence: 1.0, reason: reason)
        }

        if facts.kind == .other {
            return ClassificationDecision(category: .needsReview, confidence: 0,
                                          reason: "Not a normal photo or video.")
        }

        guard facts.visionStatus == .labeled else {
            let why: String
            switch facts.visionStatus {
            case .imageUnavailable: why = "Picture is not stored on this phone (maybe iCloud only), so it was not looked at."
            case .failed: why = "On-device picture check failed."
            default: why = "Picture was not checked."
            }
            return ClassificationDecision(category: .needsReview, confidence: 0, reason: why)
        }

        let usable = facts.labels.filter { $0.confidence >= config.minimumLabelConfidence }
        let creator = bestMatch(usable, in: config.creatorKeywords)
        let personal = bestMatch(usable, in: config.personalKeywords)

        if let creator, creator.confidence >= config.decisionThreshold,
           creator.confidence >= (personal?.confidence ?? 0) {
            return ClassificationDecision(category: .creatorContent, confidence: creator.confidence,
                                          reason: "Looks like \(pretty(creator.identifier)) (\(percent(creator.confidence))).")
        }
        if let personal, personal.confidence >= config.decisionThreshold {
            return ClassificationDecision(category: .personalPhotos, confidence: personal.confidence,
                                          reason: "Looks like \(pretty(personal.identifier)) (\(percent(personal.confidence))) — kept safe as personal.")
        }

        let top = facts.labels.max(by: { $0.confidence < $1.confidence })
        let hint = top.map { " Best guess: \(pretty($0.identifier)) (\(percent($0.confidence)))." } ?? ""
        return ClassificationDecision(category: .needsReview, confidence: top?.confidence ?? 0,
                                      reason: "Not sure what this is.\(hint)")
    }

    private static func bestMatch(_ labels: [VisionLabel], in keywords: Set<String>) -> VisionLabel? {
        labels.filter { keywords.contains($0.identifier.lowercased()) }
            .max(by: { $0.confidence < $1.confidence })
    }

    static func pretty(_ identifier: String) -> String {
        identifier.replacingOccurrences(of: "_", with: " ")
    }

    static func percent(_ value: Double) -> String {
        "\(Int((value * 100).rounded()))%"
    }

    static func formatDuration(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        return total >= 60 ? "\(total / 60)m \(total % 60)s" : "\(total)s"
    }
}
