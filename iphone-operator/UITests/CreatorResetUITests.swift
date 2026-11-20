import XCTest

/// Automated test on the iOS Simulator. Acts like a person:
/// launches the app in self-test mode, taps "Allow Full Access" on Apple's Photos box,
/// then waits for the app's own checks (FAKE test photos only) to finish.
final class CreatorResetUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    func testSelfTestWithFakePhotos() throws {
        let app = XCUIApplication()
        app.launchArguments = ["-CRSelfTest"]
        app.launch()

        // Apple's permission box may belong to SpringBoard or appear inside the app.
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let deadline = Date().addingTimeInterval(30)
        var tapped = false
        while !tapped && Date() < deadline {
            for source in [springboard, app] {
                let allow = source.buttons["Allow Full Access"]
                if allow.exists {
                    allow.tap()
                    tapped = true
                    break
                }
            }
            if !tapped { Thread.sleep(forTimeInterval: 1) }
        }
        print("Tapped Allow Full Access: \(tapped)")

        let status = app.staticTexts["selftest-status"]
        XCTAssertTrue(status.waitForExistence(timeout: 20), "Self-test banner did not appear")
        let finished = NSPredicate(format: "label BEGINSWITH 'SELFTEST PASSED' OR label BEGINSWITH 'SELFTEST FAILED'")
        let waiter = XCTNSPredicateExpectation(predicate: finished, object: status)
        let result = XCTWaiter().wait(for: [waiter], timeout: 240)

        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.lifetime = .keepAlways
        add(shot)

        print("SELFTEST RESULT: \(status.label)")
        XCTAssertEqual(result, .completed, "Self-test did not finish: \(status.label)")
        XCTAssertTrue(status.label.hasPrefix("SELFTEST PASSED"), status.label)
    }
}
