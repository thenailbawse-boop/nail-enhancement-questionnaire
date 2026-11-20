import Foundation
import Photos

enum RunMode: Sendable {
    /// The newest N items, every time. Running it twice proves "no repeats": the second run adds 0.
    case test(Int)
    /// The newest N items that were not organized before. Keeps going further back each run.
    case next(Int)

    var title: String {
        switch self {
        case .test(let n): return "Test with \(n)"
        case .next(let n): return "Organize next \(n)"
        }
    }
}

struct PreviewItem: Identifiable, Sendable {
    var facts: MediaFacts
    var decision: ClassificationDecision
    var alreadyOrganized: Bool
    var id: String { facts.id }
}

/// The operator's agent loop for Photos:
/// OBSERVE (PhotoKit + on-device Vision) → PLAN (rules) → AUTHORIZE (RiskPolicy + pause switch)
/// → EXECUTE (add to album) → VERIFY (re-read album) → LOG (ledger.json).
/// Shared by the app screen, Shortcuts, background time and the on-device AI.
actor OrganizerEngine {
    static let shared = OrganizerEngine()

    let ledger: LedgerStore
    private var running = false

    init() {
        let base = (try? FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                                 appropriateFor: nil, create: true))
            ?? FileManager.default.temporaryDirectory
        ledger = LedgerStore(url: base.appendingPathComponent("CreatorReset/ledger.json"))
    }

    nonisolated var ledgerFileURL: URL { ledger.url }

    // MARK: Preview (read-only)

    func preview(mode: RunMode) async -> [PreviewItem] {
        guard PhotoAccess.canUse else { return [] }
        let organized = await ledger.organizedAssetIDs()
        let assets: [PHAsset]
        switch mode {
        case .test(let n): assets = PhotoLibrary.newest(n)
        case .next(let n): assets = PhotoLibrary.newest(n, skipping: organized)
        }
        let config = AppSettings.classifierConfig
        return assets.map { asset in
            let facts = observe(asset)
            return PreviewItem(facts: facts, decision: MediaClassifier.classify(facts, config: config),
                               alreadyOrganized: organized.contains(asset.localIdentifier))
        }
    }

    private func observe(_ asset: PHAsset) -> MediaFacts {
        var facts = PhotoLibrary.facts(for: asset)
        let (status, labels) = VisionLabeler.label(asset)
        facts.visionStatus = status
        facts.labels = labels
        return facts
    }

    // MARK: Organize

    func run(mode: RunMode, trigger: RunTrigger, progress: (@Sendable (String) -> Void)? = nil) async throws -> RunSummary {
        guard !running else { throw OperatorError.busy }
        running = true
        defer { running = false }

        StorageReporter.rememberFirstReadingIfNeeded()
        let permission = PhotoAccess.describe(PhotoAccess.status)
        var summary = RunSummary(id: UUID(), trigger: trigger, title: mode.title, startedAt: Date())
        summary.freeBytesBefore = StorageReporter.freeBytes()

        guard PhotoAccess.canUse else {
            try await finish(&summary, entries: [], note: "Stopped: Photos access is off.")
            throw OperatorError.photosPermissionMissing
        }
        let decision = RiskPolicy.authorize(.addToAlbum, paused: AppSettings.isPaused, approved: true)
        guard decision.isAllowed else {
            try await finish(&summary, entries: [], note: "Stopped: the operator is paused.")
            throw OperatorError.paused
        }

        // OBSERVE
        progress?("Looking at your newest items…")
        let organized = await ledger.organizedAssetIDs()
        let assets: [PHAsset]
        switch mode {
        case .test(let n): assets = PhotoLibrary.newest(n)
        case .next(let n): assets = PhotoLibrary.newest(n, skipping: organized)
        }
        summary.looked = assets.count

        // PLAN
        let config = AppSettings.classifierConfig
        var entries: [LedgerEntry] = []
        var plan: [MediaCategory: [PHAsset]] = [:]
        var decisions: [String: ClassificationDecision] = [:]
        for (index, asset) in assets.enumerated() {
            if Task.isCancelled { break }
            if organized.contains(asset.localIdentifier) {
                summary.alreadyOrganized += 1
                entries.append(LedgerEntry(runID: summary.id, assetID: asset.localIdentifier, capability: .addToAlbum,
                                           target: "-", category: nil, reason: "Organized by an earlier run",
                                           confidence: nil, before: "already organized", after: "unchanged",
                                           outcome: .alreadyDone, error: nil, permission: permission))
                continue
            }
            progress?("Checking item \(index + 1) of \(assets.count) on this iPhone…")
            let facts = observe(asset)
            let choice = MediaClassifier.classify(facts, config: config)
            decisions[asset.localIdentifier] = choice
            plan[choice.category, default: []].append(asset)
        }

        // EXECUTE + VERIFY, one album at a time
        for category in MediaCategory.allCases {
            guard let group = plan[category], !group.isEmpty else { continue }
            if Task.isCancelled { break }
            progress?("Adding \(group.count) to “\(category.albumTitle)”…")
            let ids = group.map(\.localIdentifier)
            do {
                let album = try await PhotoLibrary.album(titled: category.albumTitle)
                let before = PhotoLibrary.members(of: album, among: ids)
                let toAdd = group.filter { !before.contains($0.localIdentifier) }
                try await PhotoLibrary.add(toAdd, to: album)
                let after = PhotoLibrary.members(of: album, among: ids)
                for asset in group {
                    let id = asset.localIdentifier
                    let wasIn = before.contains(id)
                    let isIn = after.contains(id)
                    let outcome: LedgerOutcome = isIn ? (wasIn ? .alreadyDone : .done) : .failed
                    switch outcome {
                    case .done: summary.added += 1
                    case .alreadyDone: summary.alreadyOrganized += 1
                    default: summary.failed += 1
                    }
                    if isIn { summary.perCategory[category.rawValue, default: 0] += 1 }
                    if category == .needsReview && isIn { summary.needsReview += 1 }
                    let choice = decisions[id]
                    entries.append(LedgerEntry(runID: summary.id, assetID: id, capability: .addToAlbum,
                                               target: category.albumTitle, category: category,
                                               reason: choice?.reason ?? "", confidence: choice?.confidence,
                                               before: wasIn ? "in album" : "not in album",
                                               after: isIn ? "in album (checked)" : "NOT in album",
                                               outcome: outcome,
                                               error: isIn ? nil : "Album check after adding did not find it",
                                               permission: permission))
                }
            } catch {
                for asset in group {
                    summary.failed += 1
                    entries.append(LedgerEntry(runID: summary.id, assetID: asset.localIdentifier, capability: .addToAlbum,
                                               target: category.albumTitle, category: category,
                                               reason: decisions[asset.localIdentifier]?.reason ?? "",
                                               confidence: decisions[asset.localIdentifier]?.confidence,
                                               before: "unknown", after: "unchanged", outcome: .failed,
                                               error: error.localizedDescription, permission: permission))
                }
            }
        }

        try await finish(&summary, entries: entries, note: Task.isCancelled ? "iOS stopped this run early; the rest will be done next time." : "")
        return summary
    }

    private func finish(_ summary: inout RunSummary, entries: [LedgerEntry], note: String) async throws {
        summary.freeBytesAfter = StorageReporter.freeBytes()
        summary.finishedAt = Date()
        if !note.isEmpty { summary.note = note }
        try await ledger.record(run: summary, entries: entries)
    }

    // MARK: Possible duplicates (metadata only, into a review album)

    func duplicateGroups(scanLimit: Int) -> [[String]] {
        DuplicateFinder.candidateGroups(PhotoLibrary.newest(scanLimit).map(PhotoLibrary.facts(for:)))
    }

    func collectDuplicates(scanLimit: Int, trigger: RunTrigger) async throws -> RunSummary {
        try await collect(title: "Find possible duplicates", album: ExtraAlbum.possibleDuplicates,
                          capability: .findDuplicates, trigger: trigger) {
            let groups = self.duplicateGroups(scanLimit: scanLimit)
            let ids = groups.flatMap { $0 }
            let note = groups.isEmpty
                ? "No obvious copies in your newest \(scanLimit) items."
                : "\(groups.count) sets of possible copies (\(ids.count) items). To merge them safely, open Photos → Albums → Utilities → Duplicates."
            return (ids, "Same size and same capture second as another item", note)
        }
    }

    /// Longest videos usually take the most space. Duration is used because exact file size
    /// is not available through Apple's public Photos API.
    func collectLongestVideos(count: Int, trigger: RunTrigger) async throws -> RunSummary {
        try await collect(title: "Find longest videos", album: ExtraAlbum.longestVideos,
                          capability: .storageReport, trigger: trigger) {
            let videos = PhotoLibrary.allVideos().sorted { $0.duration > $1.duration }.prefix(count)
            let total = videos.reduce(0) { $0 + $1.duration }
            let note = videos.isEmpty ? "No videos found."
                : "Your \(videos.count) longest videos add up to \(MediaClassifier.formatDuration(total)). Long videos are usually the biggest space users."
            return (videos.map(\.localIdentifier), "One of the longest videos", note)
        }
    }

    private func collect(title: String, album albumTitle: String, capability: OperatorCapability, trigger: RunTrigger,
                         pick: () -> (ids: [String], reason: String, note: String)) async throws -> RunSummary {
        guard !running else { throw OperatorError.busy }
        running = true
        defer { running = false }
        var summary = RunSummary(id: UUID(), trigger: trigger, title: title, startedAt: Date())
        summary.freeBytesBefore = StorageReporter.freeBytes()
        guard PhotoAccess.canUse else { throw OperatorError.photosPermissionMissing }
        guard RiskPolicy.authorize(.addToAlbum, paused: AppSettings.isPaused, approved: true).isAllowed else {
            throw OperatorError.paused
        }
        let permission = PhotoAccess.describe(PhotoAccess.status)
        let picked = pick()
        summary.looked = picked.ids.count
        var entries: [LedgerEntry] = []
        if !picked.ids.isEmpty {
            let album = try await PhotoLibrary.album(titled: albumTitle)
            let assets = PhotoLibrary.assets(ids: picked.ids)
            let before = PhotoLibrary.members(of: album, among: picked.ids)
            try await PhotoLibrary.add(assets.filter { !before.contains($0.localIdentifier) }, to: album)
            let after = PhotoLibrary.members(of: album, among: picked.ids)
            for id in picked.ids {
                let outcome: LedgerOutcome = after.contains(id) ? (before.contains(id) ? .alreadyDone : .done) : .failed
                switch outcome {
                case .done: summary.added += 1
                case .alreadyDone: summary.alreadyOrganized += 1
                default: summary.failed += 1
                }
                entries.append(LedgerEntry(runID: summary.id, assetID: id, capability: capability, target: albumTitle,
                                           category: nil, reason: picked.reason, confidence: nil,
                                           before: before.contains(id) ? "in album" : "not in album",
                                           after: after.contains(id) ? "in album (checked)" : "NOT in album",
                                           outcome: outcome, error: nil, permission: permission))
            }
        }
        try await finish(&summary, entries: entries, note: picked.note)
        return summary
    }

    // MARK: Reports (read-only)

    func libraryReport() async -> String {
        var lines: [String] = []
        lines.append("Photos access: \(PhotoAccess.describe(PhotoAccess.status)).")
        if PhotoAccess.canUse {
            lines.append("Visible to the app: \(PhotoLibrary.count(of: .image)) photos, \(PhotoLibrary.count(of: .video)) videos.")
            let organizedCount = await ledger.organizedAssetIDs().count
            lines.append("Organized so far: \(organizedCount).")
            for category in MediaCategory.allCases {
                let n = PhotoLibrary.itemCount(inAlbumTitled: category.albumTitle)
                if n > 0 { lines.append("\(category.albumTitle): \(n)") }
            }
            let dupes = PhotoLibrary.itemCount(inAlbumTitled: ExtraAlbum.possibleDuplicates)
            if dupes > 0 { lines.append("\(ExtraAlbum.possibleDuplicates): \(dupes)") }
        }
        lines.append("Free space: \(ReportFormatter.bytes(StorageReporter.freeBytes())) of \(ReportFormatter.bytes(StorageReporter.totalBytes())).")
        if let first = AppSettings.firstFreeBytes {
            lines.append(ReportFormatter.storageChange(before: first, after: StorageReporter.freeBytes()))
        }
        if let last = await ledger.lastRun() {
            lines.append("Last run (\(last.trigger.rawValue)): \(ReportFormatter.runSentence(last))")
        }
        if AppSettings.isPaused { lines.append("The operator is PAUSED. It will not change anything.") }
        return lines.joined(separator: "\n")
    }
}
