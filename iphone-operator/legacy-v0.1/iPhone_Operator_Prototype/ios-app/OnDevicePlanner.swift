import Foundation
import FoundationModels

// Optional on-device model integration, available on compatible iOS 26+ devices
// after Apple Intelligence has been enabled and the system model is ready.
// Generates a READ-ONLY plan. It does not delete, publish, or operate other apps.

@available(iOS 26.0, *)
enum OnDevicePlanner {
    static func generateReadOnlyPlan(for items: [MediaCandidate]) async throws -> String {
        let descriptions = items.prefix(20).enumerated().map { index, item in
            "\(index + 1): \(item.kind), category=\(item.category), vision=\(item.visionLabel), date=\(item.date?.description ?? "unknown")"
        }.joined(separator: "\n")
        let session = LanguageModelSession(instructions: """
            You are a privacy-first iPhone media organization assistant.
            You only receive metadata and local Vision labels.
            Give a short, practical review plan. Do not pretend to see original images.
            Never recommend deleting personal memories or taking irreversible actions.
            Limit output to 5 concise numbered actions.
            """)
        let response = try await session.respond(to: "Create a safe review plan for these items:\n\(descriptions)")
        return response.content
    }
}
