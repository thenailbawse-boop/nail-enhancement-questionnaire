import Foundation

/// Plain-English sentences used by the app screen, the Shortcuts actions and the on-device AI.
enum ReportFormatter {
    static func bytes(_ value: Int64?) -> String {
        guard let value else { return "unknown" }
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        formatter.allowedUnits = [.useGB, .useMB]
        return formatter.string(fromByteCount: value)
    }

    static func runSentence(_ run: RunSummary) -> String {
        var parts: [String] = []
        parts.append("Looked at \(run.looked) item\(run.looked == 1 ? "" : "s").")
        parts.append("Added \(run.added) to review albums.")
        if run.alreadyOrganized > 0 { parts.append("\(run.alreadyOrganized) were already organized (no repeats).") }
        if run.needsReview > 0 { parts.append("\(run.needsReview) need a human look.") }
        if run.failed > 0 { parts.append("\(run.failed) could not be confirmed.") }
        if run.blocked > 0 { parts.append("\(run.blocked) were stopped by the safety rules.") }
        parts.append("Nothing was deleted or uploaded.")
        if !run.note.isEmpty { parts.append(run.note) }
        return parts.joined(separator: " ")
    }

    static func categoryLines(_ counts: [String: Int]) -> [String] {
        MediaCategory.allCases.compactMap { category in
            guard let count = counts[category.rawValue], count > 0 else { return nil }
            return "\(category.plainName): \(count)"
        }
    }

    /// Storage change between two readings. Honest about what caused it.
    static func storageChange(before: Int64?, after: Int64?) -> String {
        guard let before, let after else { return "Storage change: unknown." }
        let delta = after - before
        if delta == 0 { return "Free space did not change." }
        if delta > 0 {
            return "Free space went up by \(bytes(delta)). (This app never deletes, so this came from something else — like emptying Recently Deleted.)"
        }
        return "Free space went down by \(bytes(-delta)) (new photos, apps or updates use space too)."
    }

    static func needsReviewReasonSummary(_ decisions: [ClassificationDecision]) -> String {
        let review = decisions.filter { $0.category == .needsReview }
        if review.isEmpty { return "Nothing needs review." }
        return "\(review.count) item\(review.count == 1 ? "" : "s") need review."
    }
}
