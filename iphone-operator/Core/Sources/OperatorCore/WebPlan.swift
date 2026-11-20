import Foundation

/// The only things the Safari operator is allowed to do on a web page.
/// Same rules as SafariExtension/Resources/plan-validator.js (kept in sync by tests).
struct WebStep: Codable, Hashable, Sendable {
    var action: String          // "scroll" | "type" | "click"
    var target: String?         // element id from the latest Inspect, e.g. "3"
    var text: String?           // only for "type"
    var direction: String?      // only for "scroll": "up" | "down"
    var expectLabel: String?    // label seen at inspect time; executor fails if it changed
}

struct WebPlan: Codable, Hashable, Sendable {
    var summary: String?
    var steps: [WebStep]
}

struct WebControl: Codable, Hashable, Sendable {
    var id: String
    var tag: String
    var type: String
    var label: String
}

enum WebPlanValidator {
    static let maxSteps = 20
    static let maxText = 512
    static let allowedActions: Set<String> = ["scroll", "type", "click"]

    /// Words that mean "this changes something that matters". Clicks on these are refused,
    /// and goals containing them are not planned. A person does these by hand.
    static let riskyWords = [
        "delete", "remove", "archive", "publish", "post now", "submit", "send", "buy", "pay",
        "checkout", "purchase", "transfer", "withdraw", "confirm", "sign out", "log out",
        "unsubscribe", "permanently", "erase", "discard", "save changes", "place order",
        "password", "credit card", "bank"
    ]

    static func riskyWord(in text: String) -> String? {
        let lower = text.lowercased()
        return riskyWords.first { lower.contains($0) }
    }

    struct Result: Equatable {
        var plan: WebPlan
        var errors: [String]
        var isValid: Bool { errors.isEmpty }
    }

    /// Checks a plan against the allowlist and the latest page inspection.
    /// Anything unclear fails closed.
    static func validate(_ plan: WebPlan, controls: [WebControl]) -> Result {
        var errors: [String] = []
        if plan.steps.isEmpty { errors.append("The plan has no steps.") }
        if plan.steps.count > maxSteps { errors.append("Too many steps (max \(maxSteps)).") }
        let byID = Dictionary(controls.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })

        for (index, step) in plan.steps.prefix(maxSteps).enumerated() {
            let n = index + 1
            guard allowedActions.contains(step.action) else {
                errors.append("Step \(n): \"\(step.action)\" is not an allowed action.")
                continue
            }
            switch step.action {
            case "scroll":
                if let d = step.direction, d != "up", d != "down" {
                    errors.append("Step \(n): scroll direction must be up or down.")
                }
            case "type", "click":
                guard let target = step.target, target.range(of: #"^\d{1,3}$"#, options: .regularExpression) != nil else {
                    errors.append("Step \(n): needs a target number from the latest Inspect.")
                    continue
                }
                guard let control = byID[target] else {
                    errors.append("Step \(n): target \(target) is not on the page right now. Inspect again.")
                    continue
                }
                if step.action == "type" {
                    guard let text = step.text, !text.isEmpty else {
                        errors.append("Step \(n): type needs text.")
                        continue
                    }
                    if text.count > maxText { errors.append("Step \(n): text is longer than \(maxText) characters.") }
                    let typable = (control.tag == "input" && !["checkbox", "radio", "submit", "button", "password", "hidden", "file"].contains(control.type.lowercased()))
                        || control.tag == "textarea"
                    if !typable { errors.append("Step \(n): target \(target) is not a text box.") }
                } else {
                    if let word = riskyWord(in: control.label) {
                        errors.append("Step \(n): \"\(control.label)\" looks risky (\(word)). Do that one yourself.")
                    }
                    if control.type.lowercased() == "submit" {
                        errors.append("Step \(n): submitting forms is not allowed.")
                    }
                }
            default:
                break
            }
        }
        return Result(plan: plan, errors: errors)
    }
}
