import XCTest
@testable import OperatorCore

final class DuplicateFinderTests: XCTestCase {
    func testFindsSameSecondSameSizeCopies() {
        let date = Date(timeIntervalSince1970: 1_700_000_000.4)
        let a = MediaFacts(id: "a", kind: .photo, pixelWidth: 100, pixelHeight: 200, creationDate: date)
        let b = MediaFacts(id: "b", kind: .photo, pixelWidth: 100, pixelHeight: 200, creationDate: date.addingTimeInterval(0.3))
        let c = MediaFacts(id: "c", kind: .photo, pixelWidth: 100, pixelHeight: 201, creationDate: date)
        let d = MediaFacts(id: "d", kind: .video, pixelWidth: 100, pixelHeight: 200, creationDate: date)
        let noDate = MediaFacts(id: "e", kind: .photo, pixelWidth: 100, pixelHeight: 200, creationDate: nil)
        XCTAssertEqual(DuplicateFinder.candidateGroups([a, b, c, d, noDate]), [["a", "b"]])
    }

    func testDifferentVideoLengthsAreNotDuplicates() {
        let date = Date(timeIntervalSince1970: 1_700_000_000)
        let a = MediaFacts(id: "a", kind: .video, pixelWidth: 1080, pixelHeight: 1920, duration: 10, creationDate: date)
        let b = MediaFacts(id: "b", kind: .video, pixelWidth: 1080, pixelHeight: 1920, duration: 11, creationDate: date)
        XCTAssertTrue(DuplicateFinder.candidateGroups([a, b]).isEmpty)
    }
}

final class RiskPolicyTests: XCTestCase {
    func testForbiddenActionsAreAlwaysBlocked() {
        for capability in [OperatorCapability.deleteUserMedia, .uploadMedia, .instagramArchive, .instagramDelete,
                           .instagramPublish, .webSubmitForm, .webEnterPassword, .webPurchase] {
            XCTAssertEqual(RiskPolicy.tier(of: capability), .forbidden, "\(capability)")
            XCTAssertFalse(RiskPolicy.authorize(capability, paused: false, approved: true).isAllowed, "\(capability)")
        }
    }

    func testPauseStopsChangesButNotLooking() {
        XCTAssertTrue(RiskPolicy.authorize(.scanLibrary, paused: true, approved: false).isAllowed)
        XCTAssertFalse(RiskPolicy.authorize(.addToAlbum, paused: true, approved: true).isAllowed)
        XCTAssertTrue(RiskPolicy.authorize(.addToAlbum, paused: false, approved: false).isAllowed)
    }

    func testConsequentialNeedsApproval() {
        if case .needsApproval = RiskPolicy.authorize(.removeAppTestPhotos, paused: false, approved: false) {} else {
            XCTFail("Expected needsApproval")
        }
        XCTAssertTrue(RiskPolicy.authorize(.removeAppTestPhotos, paused: false, approved: true).isAllowed)
    }

    func testEveryCapabilityHasATier() {
        for capability in OperatorCapability.allCases { _ = RiskPolicy.tier(of: capability) }
    }
}
