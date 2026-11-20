import XCTest
@testable import OperatorCore

final class ClassifierTests: XCTestCase {
    private func photo(_ labels: [(String, Double)], status: VisionStatus = .labeled) -> MediaFacts {
        MediaFacts(id: UUID().uuidString, kind: .photo, pixelWidth: 3024, pixelHeight: 4032,
                   creationDate: Date(), visionStatus: status,
                   labels: labels.map { VisionLabel(identifier: $0.0, confidence: $0.1) })
    }

    func testScreenshotWinsOverEverything() {
        var facts = photo([("food", 0.99)])
        facts.isScreenshot = true
        XCTAssertEqual(MediaClassifier.classify(facts).category, .screenshots)
    }

    func testVideosAlwaysGoToVideosAndNeverClaimContentUnderstanding() {
        let facts = MediaFacts(id: "v", kind: .video, pixelWidth: 1080, pixelHeight: 1920, duration: 14)
        let decision = MediaClassifier.classify(facts)
        XCTAssertEqual(decision.category, .videos)
        XCTAssertTrue(decision.reason.contains("Reel"))
        XCTAssertTrue(decision.reason.contains("not analyzed"))
    }

    func testConfidentCreatorLabel() {
        let decision = MediaClassifier.classify(photo([("cosmetics", 0.82), ("people", 0.40)]))
        XCTAssertEqual(decision.category, .creatorContent)
        XCTAssertEqual(decision.confidence, 0.82, accuracy: 0.0001)
    }

    func testConfidentPersonalLabelIsKeptSafe() {
        let decision = MediaClassifier.classify(photo([("dog", 0.91), ("food", 0.31)]))
        XCTAssertEqual(decision.category, .personalPhotos)
    }

    func testUncertainGoesToNeedsReview() {
        let decision = MediaClassifier.classify(photo([("food", 0.42), ("structure", 0.6)]))
        XCTAssertEqual(decision.category, .needsReview)
        XCTAssertTrue(decision.reason.contains("structure"))
    }

    func testMissingLocalImageGoesToNeedsReview() {
        let decision = MediaClassifier.classify(photo([], status: .imageUnavailable))
        XCTAssertEqual(decision.category, .needsReview)
        XCTAssertTrue(decision.reason.contains("iCloud"))
    }

    func testCustomKeywordsChangeTheAnswer() {
        var config = ClassifierConfig.standard
        config.creatorKeywords = ClassifierConfig.parseKeywords(" Car, motor vehicle ,")
        XCTAssertEqual(config.creatorKeywords, ["car", "motor_vehicle"])
        XCTAssertEqual(MediaClassifier.classify(photo([("car", 0.7)]), config: config).category, .creatorContent)
    }

    func testDeterministic() {
        let facts = photo([("cake", 0.7), ("people", 0.7)])
        let a = MediaClassifier.classify(facts)
        let b = MediaClassifier.classify(facts)
        XCTAssertEqual(a, b)
        XCTAssertEqual(a.category, .creatorContent, "Ties go to creator content")
    }

    func testAlbumTitlesShareOnePrefix() {
        for category in MediaCategory.allCases {
            XCTAssertTrue(category.albumTitle.hasPrefix("Reset · "))
        }
        XCTAssertEqual(Set(MediaCategory.allCases.map(\.albumTitle)).count, MediaCategory.allCases.count)
    }
}
