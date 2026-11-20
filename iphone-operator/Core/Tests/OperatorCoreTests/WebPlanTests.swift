import XCTest
@testable import OperatorCore

final class WebPlanTests: XCTestCase {
    let controls = [
        WebControl(id: "0", tag: "input", type: "search", label: "Search"),
        WebControl(id: "1", tag: "a", type: "", label: "More information"),
        WebControl(id: "2", tag: "button", type: "button", label: "Delete account"),
        WebControl(id: "3", tag: "input", type: "submit", label: "Go"),
        WebControl(id: "4", tag: "input", type: "checkbox", label: "Remember")
    ]

    func testGoodPlanPasses() {
        let plan = WebPlan(summary: nil, steps: [
            WebStep(action: "type", target: "0", text: "nail art"),
            WebStep(action: "scroll", direction: "down"),
            WebStep(action: "click", target: "1")
        ])
        XCTAssertTrue(WebPlanValidator.validate(plan, controls: controls).isValid)
    }

    func testRejectsUnknownActionsAndScripts() {
        let plan = WebPlan(summary: nil, steps: [WebStep(action: "eval", text: "alert(1)")])
        XCTAssertFalse(WebPlanValidator.validate(plan, controls: controls).isValid)
    }

    func testRejectsRiskyClicksSubmitAndStaleTargets() {
        for step in [WebStep(action: "click", target: "2"), WebStep(action: "click", target: "3"),
                     WebStep(action: "click", target: "99"), WebStep(action: "click", target: "1; drop"),
                     WebStep(action: "type", target: "4", text: "x"), WebStep(action: "type", target: "0", text: "")] {
            XCTAssertFalse(WebPlanValidator.validate(WebPlan(summary: nil, steps: [step]), controls: controls).isValid, "\(step)")
        }
    }

    func testStepAndTextLimits() {
        let many = WebPlan(summary: nil, steps: Array(repeating: WebStep(action: "scroll", direction: "down"), count: 21))
        XCTAssertFalse(WebPlanValidator.validate(many, controls: controls).isValid)
        let long = WebPlan(summary: nil, steps: [WebStep(action: "type", target: "0", text: String(repeating: "a", count: 513))])
        XCTAssertFalse(WebPlanValidator.validate(long, controls: controls).isValid)
        XCTAssertFalse(WebPlanValidator.validate(WebPlan(summary: nil, steps: []), controls: controls).isValid)
    }

    func testRiskyGoalDetection() {
        XCTAssertEqual(WebPlanValidator.riskyWord(in: "Please DELETE my old posts"), "delete")
        XCTAssertNil(WebPlanValidator.riskyWord(in: "find nail art ideas"))
    }

    /// The JS validator (plan-validator.js) must use the same risky word list.
    func testRiskyWordsMatchJavaScriptValidator() throws {
        let here = URL(fileURLWithPath: #filePath)
        let js = here.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("SafariExtension/Resources/plan-validator.js")
        let source = try String(contentsOf: js, encoding: .utf8)
        for word in WebPlanValidator.riskyWords {
            XCTAssertTrue(source.contains("\"\(word)\""), "plan-validator.js is missing \"\(word)\"")
        }
    }
}
