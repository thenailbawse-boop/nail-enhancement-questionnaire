import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Holds an organize request the AI proposed, until the owner taps Approve.
/// The AI can never organize by itself — it can only ask.
actor ProposalBox {
    static let shared = ProposalBox()
    private var pending: Int?

    func propose(_ count: Int) { pending = count }
    func take() -> Int? { defer { pending = nil }; return pending }
    func peek() -> Int? { pending }
}

#if canImport(FoundationModels)

// MARK: Tools the on-device model may call. All are read-only except "propose", which only asks.

@available(iOS 26.0, *)
struct LibraryReportTool: Tool {
    let name = "getLibraryReport"
    let description = "Read-only. Gets photo and video counts, review album counts, free storage and the last organizer run."

    @Generable
    struct Arguments {
        @Guide(description: "Always true.")
        var includeStorage: Bool
    }

    func call(arguments: Arguments) async throws -> String {
        await OrganizerEngine.shared.libraryReport()
    }
}

@available(iOS 26.0, *)
struct PreviewBatchTool: Tool {
    let name = "previewNextBatch"
    let description = "Read-only. Looks at the next not-yet-organized photos and videos and says which review album each would go to. Changes nothing."

    @Generable
    struct Arguments {
        @Guide(description: "How many items to preview, from 1 to 30.")
        var count: Int
    }

    func call(arguments: Arguments) async throws -> String {
        let n = min(max(arguments.count, 1), 30)
        let items = await OrganizerEngine.shared.preview(mode: .next(n))
        if items.isEmpty { return "Nothing new to preview (or Photos access is off)." }
        var counts: [MediaCategory: Int] = [:]
        for item in items { counts[item.decision.category, default: 0] += 1 }
        let tally = MediaCategory.allCases.compactMap { c in counts[c].map { "\(c.plainName): \($0)" } }.joined(separator: ", ")
        let examples = items.prefix(4).map { "- \($0.decision.category.plainName): \($0.decision.reason)" }.joined(separator: "\n")
        return "Preview of \(items.count) items (nothing changed). \(tally)\nExamples:\n\(examples)"
    }
}

@available(iOS 26.0, *)
struct DuplicateCountTool: Tool {
    let name = "countPossibleDuplicates"
    let description = "Read-only. Counts sets of likely copies (same size, same capture second) among the newest items. Changes nothing."

    @Generable
    struct Arguments {
        @Guide(description: "How many newest items to check, from 100 to 2000.")
        var scanLimit: Int
    }

    func call(arguments: Arguments) async throws -> String {
        let n = min(max(arguments.scanLimit, 100), 2000)
        let groups = await OrganizerEngine.shared.duplicateGroups(scanLimit: n)
        return "Found \(groups.count) sets of possible copies (\(groups.reduce(0) { $0 + $1.count }) items) in the newest \(n). Nothing changed. Apple's Photos → Utilities → Duplicates can merge true copies."
    }
}

@available(iOS 26.0, *)
struct ProposeOrganizeTool: Tool {
    let name = "proposeOrganize"
    let description = "Does NOT organize. Shows the owner an Approve button for organizing the next N items into review albums. Use when the owner asks to organize."

    @Generable
    struct Arguments {
        @Guide(description: "How many items to organize, from 1 to 200.")
        var count: Int
    }

    func call(arguments: Arguments) async throws -> String {
        let n = min(max(arguments.count, 1), 200)
        await ProposalBox.shared.propose(n)
        return "An Approve button for organizing \(n) items is now shown to the owner. Nothing has been organized yet."
    }
}

@available(iOS 26.0, *)
final class AssistantSession {
    private let session = LanguageModelSession(
        tools: [LibraryReportTool(), PreviewBatchTool(), DuplicateCountTool(), ProposeOrganizeTool()],
        instructions: """
        You are Creator Reset, a helper inside an iPhone app that organizes the owner's photos.
        You can only use your tools. You cannot see photos, open other apps, use Instagram, or delete anything.
        Organizing means adding items to review albums; it does not free storage.
        To free storage the owner must delete things herself, for example in Photos → Utilities → Duplicates, then empty Recently Deleted.
        When the owner asks to organize, call proposeOrganize and tell her to tap Approve.
        Never say something was done unless a tool result says so.
        Answer in 2 to 5 short, friendly sentences a 10-year-old could follow.
        """
    )

    func ask(_ text: String) async throws -> String {
        try await session.respond(to: text).content
    }
}

#endif

/// Screen model for the "Ask" tab.
@MainActor
final class AssistantChat: ObservableObject {
    struct Line: Identifiable {
        let id = UUID()
        let fromOwner: Bool
        let text: String
    }

    @Published var lines: [Line] = []
    @Published var thinking = false
    @Published var pendingCount: Int?
    let available = OnDeviceAIStatus.isAvailable
    let statusMessage = OnDeviceAIStatus.message

    private var holder: AnyObject?

    func send(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !thinking else { return }
        lines.append(Line(fromOwner: true, text: trimmed))
        thinking = true
        defer { thinking = false }
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *), available {
            let session: AssistantSession
            if let existing = holder as? AssistantSession {
                session = existing
            } else {
                session = AssistantSession()
                holder = session
            }
            do {
                let answer = try await session.ask(trimmed)
                lines.append(Line(fromOwner: false, text: answer))
            } catch {
                holder = nil // start fresh next time (e.g. conversation got too long)
                lines.append(Line(fromOwner: false, text: "Sorry, the on-device AI had a problem: \(error.localizedDescription)"))
            }
            pendingCount = await ProposalBox.shared.peek()
            return
        }
        #endif
        lines.append(Line(fromOwner: false, text: statusMessage))
    }

    /// Owner tapped Approve: only now does the organizer run.
    func approve(using model: OperatorModel) async {
        guard let count = await ProposalBox.shared.take() else { return }
        pendingCount = nil
        await model.runOrganizer(count: count, trigger: .assistant)
        lines.append(Line(fromOwner: false, text: "Done after your OK. \(model.message)"))
    }

    func decline() async {
        _ = await ProposalBox.shared.take()
        pendingCount = nil
        lines.append(Line(fromOwner: false, text: "Okay — nothing was changed."))
    }
}
