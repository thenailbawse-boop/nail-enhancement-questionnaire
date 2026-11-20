import Foundation

/// Who started a run. Shown in the results screen so the owner can see what ran by itself.
enum RunTrigger: String, Codable, Sendable {
    case app = "In the app"
    case shortcut = "Shortcuts"
    case background = "iOS background time"
    case assistant = "On-device AI (after your OK)"
}

enum LedgerOutcome: String, Codable, Sendable {
    case done            // change made and checked
    case alreadyDone     // nothing to do — it was already in place (idempotent re-run)
    case skipped         // left alone on purpose
    case failed          // tried; the check afterwards shows it did not happen
    case blocked         // safety policy or permission stopped it
}

/// One line in the action log: what we planned, what was true before, what is true after.
struct LedgerEntry: Codable, Hashable, Identifiable, Sendable {
    var id: UUID = UUID()
    var runID: UUID
    var timestamp: Date = Date()
    var assetID: String
    var capability: OperatorCapability
    var target: String
    var category: MediaCategory?
    var reason: String
    var confidence: Double?
    var before: String
    var after: String
    var outcome: LedgerOutcome
    var error: String?
    var permission: String
}

struct RunSummary: Codable, Hashable, Identifiable, Sendable {
    var id: UUID
    var trigger: RunTrigger
    var title: String
    var startedAt: Date
    var finishedAt: Date?
    var looked: Int = 0
    var added: Int = 0
    var alreadyOrganized: Int = 0
    var needsReview: Int = 0
    var failed: Int = 0
    var blocked: Int = 0
    var perCategory: [String: Int] = [:]
    var freeBytesBefore: Int64?
    var freeBytesAfter: Int64?
    var note: String = ""
}

struct LedgerFile: Codable, Sendable {
    var version: Int = 1
    var runs: [RunSummary] = []
    var entries: [LedgerEntry] = []
}

/// The action log on disk (a JSON file in the app's private folder).
/// Nothing in it leaves the phone unless the owner taps Share.
actor LedgerStore {
    nonisolated let url: URL
    let maxEntries: Int
    let maxRuns: Int
    private var file: LedgerFile
    private var organizedCache: Set<String>

    init(url: URL, maxEntries: Int = 5000, maxRuns: Int = 300) {
        self.url = url
        self.maxEntries = maxEntries
        self.maxRuns = maxRuns
        let loaded = (try? Data(contentsOf: url)).flatMap { try? LedgerStore.decoder.decode(LedgerFile.self, from: $0) } ?? LedgerFile()
        self.file = loaded
        self.organizedCache = LedgerStore.organizedIDs(in: loaded.entries)
    }

    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        return e
    }()

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    private static func organizedIDs(in entries: [LedgerEntry]) -> Set<String> {
        Set(entries.filter { $0.capability == .addToAlbum && ($0.outcome == .done || $0.outcome == .alreadyDone) }
            .map(\.assetID))
    }

    /// True when this item was already filed into a review album by an earlier run.
    /// Used so repeat runs never redo work — and never re-add something the owner
    /// later took out of an album by hand.
    func isOrganized(_ assetID: String) -> Bool { organizedCache.contains(assetID) }

    func organizedAssetIDs() -> Set<String> { organizedCache }

    func record(run: RunSummary, entries newEntries: [LedgerEntry]) throws {
        file.entries.append(contentsOf: newEntries)
        if let index = file.runs.firstIndex(where: { $0.id == run.id }) {
            file.runs[index] = run
        } else {
            file.runs.append(run)
        }
        if file.entries.count > maxEntries {
            // Trim the oldest lines but remember what they organized (idempotency survives trimming).
            let overflow = file.entries.count - maxEntries
            let dropped = file.entries.prefix(overflow)
            organizedCache.formUnion(LedgerStore.organizedIDs(in: Array(dropped)))
            file.entries.removeFirst(overflow)
            // Keep one compact marker per trimmed organized asset so the cache rebuilds on next launch.
            let markers = LedgerStore.organizedIDs(in: Array(dropped)).subtracting(LedgerStore.organizedIDs(in: file.entries)).map {
                LedgerEntry(runID: run.id, assetID: $0, capability: .addToAlbum, target: "(trimmed)", category: nil,
                            reason: "Older log line trimmed", confidence: nil, before: "", after: "", outcome: .alreadyDone,
                            error: nil, permission: "")
            }
            file.entries.insert(contentsOf: markers, at: 0)
        }
        if file.runs.count > maxRuns { file.runs.removeFirst(file.runs.count - maxRuns) }
        organizedCache.formUnion(LedgerStore.organizedIDs(in: newEntries))
        try save()
    }

    func runs() -> [RunSummary] { file.runs.sorted { $0.startedAt > $1.startedAt } }

    func entries(for runID: UUID) -> [LedgerEntry] { file.entries.filter { $0.runID == runID } }

    func allEntries() -> [LedgerEntry] { file.entries }

    func lastRun() -> RunSummary? { file.runs.max { $0.startedAt < $1.startedAt } }

    /// Starts a fresh log. Does not touch Photos.
    func reset() throws {
        file = LedgerFile()
        organizedCache = []
        try save()
    }

    private func save() throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let data = try LedgerStore.encoder.encode(file)
        try data.write(to: url, options: [.atomic])
    }
}
