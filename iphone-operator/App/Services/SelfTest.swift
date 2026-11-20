import Foundation
import Photos

#if DEBUG
/// Automatic smoke test for the iOS Simulator (used by the GitHub build check).
/// Runs only in Debug builds and only when launched with the argument -CRSelfTest.
/// It uses FAKE test photos only. Writes Documents/selftest.json with pass/fail per check.
/// Shown on screen during a self-test so the UI test (UITests/) can read the result.
@MainActor
final class SelfTestStatus: ObservableObject {
    static let shared = SelfTestStatus()
    @Published var text = "SELFTEST WAITING"
}

enum SelfTest {
    static var requested: Bool { ProcessInfo.processInfo.arguments.contains("-CRSelfTest") }

    struct Check: Codable {
        var name: String
        var passed: Bool
        var detail: String
    }

    struct Report: Codable {
        var finishedAt: Date
        var passed: Bool
        var checks: [Check]
    }

    static func runIfRequested() async {
        guard requested else { return }
        await MainActor.run { SelfTestStatus.shared.text = "SELFTEST RUNNING" }
        var checks: [Check] = []
        func check(_ name: String, _ passed: Bool, _ detail: String) {
            checks.append(Check(name: name, passed: passed, detail: detail))
        }

        let status = await PhotoAccess.request()
        check("photos permission", PhotoAccess.allowed(status), PhotoAccess.describe(status))

        if PhotoAccess.allowed(status) {
            do {
                AppSettings.isPaused = false
                try await OrganizerEngine.shared.ledger.reset()
                let made = try await TestPhotoFactory.addSampleSet()
                check("fake photos created", made == TestPhotoFactory.specs.count, "\(made) created")

                let first = try await OrganizerEngine.shared.run(mode: .test(5), trigger: .app)
                check("first run filed 5 items", first.looked == 5 && first.added + first.alreadyOrganized == 5 && first.failed == 0,
                      ReportFormatter.runSentence(first))

                let entries = await OrganizerEngine.shared.ledger.entries(for: first.id)
                let verified = entries.filter { $0.outcome == .done }.allSatisfy { $0.after.contains("checked") }
                check("every add was re-checked in Photos", verified && !entries.isEmpty, "\(entries.count) log lines")

                let second = try await OrganizerEngine.shared.run(mode: .test(5), trigger: .app)
                check("second run adds zero (no repeats)", second.added == 0 && second.alreadyOrganized == 5,
                      ReportFormatter.runSentence(second))

                let groups = await OrganizerEngine.shared.duplicateGroups(scanLimit: 200)
                check("duplicate pair found", groups.contains { $0.count >= 2 }, "\(groups.count) groups")

                AppSettings.isPaused = true
                var pausedBlocked = false
                do { _ = try await OrganizerEngine.shared.run(mode: .next(5), trigger: .shortcut) } catch OperatorError.paused { pausedBlocked = true }
                AppSettings.isPaused = false
                check("pause switch blocks changes", pausedBlocked, pausedBlocked ? "blocked" : "NOT blocked")

                let report = await OrganizerEngine.shared.libraryReport()
                check("library report", report.contains("Free space"), report.replacingOccurrences(of: "\n", with: " | "))
            } catch {
                check("no errors", false, error.localizedDescription)
            }
        }

        let report = Report(finishedAt: Date(), passed: checks.allSatisfy(\.passed), checks: checks)
        let lines = checks.map { "\($0.passed ? "PASS" : "FAIL") \($0.name): \($0.detail)" }.joined(separator: " || ")
        await MainActor.run {
            SelfTestStatus.shared.text = (report.passed ? "SELFTEST PASSED || " : "SELFTEST FAILED || ") + lines
        }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(report),
           let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first {
            try? data.write(to: docs.appendingPathComponent("selftest.json"), options: .atomic)
        }
    }
}
#endif
