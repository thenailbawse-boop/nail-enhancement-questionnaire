import AppIntents
import Foundation

// Actions that appear in Apple's Shortcuts app under "Creator Reset".
// They can be run by tapping, by Siri, or by a Shortcuts Personal Automation (e.g. every night).
// They work only inside this app's own Photos permission. They cannot control other apps.

struct OrganizeRecentMediaIntent: AppIntent {
    static let title: LocalizedStringResource = "Organize Recent Media"
    static let description = IntentDescription(
        "Files your newest not-yet-organized photos and videos into Creator Reset review albums. Never deletes, edits or uploads anything."
    )
    static let openAppWhenRun: Bool = false

    @Parameter(title: "How many items", default: 20)
    var count: Int

    static var parameterSummary: some ParameterSummary {
        Summary("Organize \(\.$count) recent items")
    }

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        guard PhotoAccess.canUse else {
            let text = "Photos access is off. Open Creator Reset and tap Allow Photos."
            return .result(value: text, dialog: "\(text)")
        }
        let limit = min(max(count, 1), 200)
        do {
            let run = try await OrganizerEngine.shared.run(mode: .next(limit), trigger: .shortcut)
            let text = ReportFormatter.runSentence(run)
            return .result(value: text, dialog: "\(text)")
        } catch {
            let text = error.localizedDescription
            return .result(value: text, dialog: "\(text)")
        }
    }
}

struct GetLibraryReportIntent: AppIntent {
    static let title: LocalizedStringResource = "Get Library Report"
    static let description = IntentDescription(
        "Read-only. Returns counts, free space and the last run as text. You can pass this text to ChatGPT or Apple Intelligence in Shortcuts — it contains numbers only, never photos."
    )
    static let openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        let text = await OrganizerEngine.shared.libraryReport()
        return .result(value: text, dialog: "\(text)")
    }
}

struct FindPossibleDuplicatesIntent: AppIntent {
    static let title: LocalizedStringResource = "Find Possible Duplicates"
    static let description = IntentDescription(
        "Puts likely copies (same size, same second) from your newest 2,000 items into “Reset · Possible Duplicates” for you to check. Deletes nothing."
    )
    static let openAppWhenRun: Bool = false

    func perform() async throws -> some IntentResult & ReturnsValue<String> & ProvidesDialog {
        do {
            let run = try await OrganizerEngine.shared.collectDuplicates(scanLimit: 2000, trigger: .shortcut)
            let text = run.note
            return .result(value: text, dialog: "\(text)")
        } catch {
            let text = error.localizedDescription
            return .result(value: text, dialog: "\(text)")
        }
    }
}

struct CreatorResetShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: OrganizeRecentMediaIntent(),
            phrases: ["Organize my photos with \(.applicationName)", "Run \(.applicationName)"],
            shortTitle: "Organize Media",
            systemImageName: "photo.on.rectangle.angled"
        )
        AppShortcut(
            intent: GetLibraryReportIntent(),
            phrases: ["Get my \(.applicationName) report"],
            shortTitle: "Library Report",
            systemImageName: "chart.bar.doc.horizontal"
        )
        AppShortcut(
            intent: FindPossibleDuplicatesIntent(),
            phrases: ["Find duplicates with \(.applicationName)"],
            shortTitle: "Find Duplicates",
            systemImageName: "square.on.square"
        )
    }
}
