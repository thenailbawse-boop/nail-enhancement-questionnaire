import XCTest
@testable import OperatorCore

final class LedgerTests: XCTestCase {
    private func tempURL() -> URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("ledger-\(UUID().uuidString)/ledger.json")
    }

    private func entry(_ run: UUID, _ asset: String, _ outcome: LedgerOutcome) -> LedgerEntry {
        LedgerEntry(runID: run, assetID: asset, capability: .addToAlbum, target: "Reset · Videos", category: .videos,
                    reason: "test", confidence: 1, before: "not in album", after: "in album", outcome: outcome,
                    error: nil, permission: "Full access")
    }

    func testRecordsPersistAndReload() async throws {
        let url = tempURL()
        let store = LedgerStore(url: url)
        let run = RunSummary(id: UUID(), trigger: .app, title: "Test", startedAt: Date())
        try await store.record(run: run, entries: [entry(run.id, "A", .done), entry(run.id, "B", .failed)])

        let reloaded = LedgerStore(url: url)
        let organizedA = await reloaded.isOrganized("A")
        let organizedB = await reloaded.isOrganized("B")
        XCTAssertTrue(organizedA)
        XCTAssertFalse(organizedB, "Failed adds are retried next time")
        let runs = await reloaded.runs()
        XCTAssertEqual(runs.count, 1)
        let entries = await reloaded.entries(for: run.id)
        XCTAssertEqual(entries.count, 2)
    }

    func testTrimmingKeepsIdempotency() async throws {
        let store = LedgerStore(url: tempURL(), maxEntries: 10)
        let run = RunSummary(id: UUID(), trigger: .app, title: "Big", startedAt: Date())
        let entries = (0..<25).map { entry(run.id, "asset-\($0)", .done) }
        try await store.record(run: run, entries: entries)
        for i in 0..<25 {
            let organized = await store.isOrganized("asset-\(i)")
            XCTAssertTrue(organized, "asset-\(i)")
        }
        let reloaded = LedgerStore(url: store.url, maxEntries: 10)
        let first = await reloaded.isOrganized("asset-0")
        XCTAssertTrue(first, "Trimmed entries still count after relaunch")
    }

    func testUpdatingARunDoesNotDuplicateIt() async throws {
        let store = LedgerStore(url: tempURL())
        var run = RunSummary(id: UUID(), trigger: .shortcut, title: "Run", startedAt: Date())
        try await store.record(run: run, entries: [])
        run.added = 3
        try await store.record(run: run, entries: [])
        let runs = await store.runs()
        XCTAssertEqual(runs.count, 1)
        XCTAssertEqual(runs.first?.added, 3)
    }

    func testRunSentenceIsHonest() {
        var run = RunSummary(id: UUID(), trigger: .app, title: "x", startedAt: Date())
        run.looked = 5; run.added = 0; run.alreadyOrganized = 5
        let text = ReportFormatter.runSentence(run)
        XCTAssertTrue(text.contains("Added 0"))
        XCTAssertTrue(text.contains("already organized"))
        XCTAssertTrue(text.contains("Nothing was deleted"))
    }

    func testStorageChangeWording() {
        XCTAssertTrue(ReportFormatter.storageChange(before: 100, after: 100).contains("did not change"))
        XCTAssertTrue(ReportFormatter.storageChange(before: 0, after: 5_000_000_000).contains("never deletes"))
        XCTAssertTrue(ReportFormatter.storageChange(before: nil, after: 1).contains("unknown"))
    }
}
