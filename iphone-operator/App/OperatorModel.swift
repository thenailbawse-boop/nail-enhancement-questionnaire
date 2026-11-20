import Foundation
import Photos
import SwiftUI
import UIKit

/// Everything the screens show, and the buttons' actions.
@MainActor
final class OperatorModel: ObservableObject {
    @Published var permission: PHAuthorizationStatus = PhotoAccess.status
    @Published var busy = false
    @Published var progress = ""
    @Published var message = "Start with step 1: Allow Photos."
    @Published var lastRun: RunSummary?
    @Published var runs: [RunSummary] = []
    @Published var preview: [PreviewItem] = []
    @Published var freeBytes: Int64?
    @Published var totalBytes: Int64?
    @Published var testPhotoCount = AppSettings.testPhotoIDs.count
    @Published var batchSize = 20

    @Published var isPaused: Bool = AppSettings.isPaused {
        didSet { AppSettings.isPaused = isPaused }
    }

    @Published var backgroundEnabled: Bool = AppSettings.backgroundEnabled {
        didSet {
            AppSettings.backgroundEnabled = backgroundEnabled
            BackgroundOrganizer.scheduleIfEnabled()
        }
    }

    @Published var creatorKeywords: String = AppSettings.creatorKeywordsText {
        didSet { AppSettings.creatorKeywordsText = creatorKeywords }
    }

    var canUsePhotos: Bool { PhotoAccess.allowed(permission) }
    var permissionText: String { PhotoAccess.describe(permission) }
    var ledgerURL: URL { OrganizerEngine.shared.ledgerFileURL }

    func refresh() async {
        permission = PhotoAccess.status
        StorageReporter.rememberFirstReadingIfNeeded()
        freeBytes = StorageReporter.freeBytes()
        totalBytes = StorageReporter.totalBytes()
        runs = await OrganizerEngine.shared.ledger.runs()
        lastRun = runs.first
        testPhotoCount = AppSettings.testPhotoIDs.count
    }

    func requestAccess() async {
        permission = await PhotoAccess.request()
        message = canUsePhotos
            ? "Photos access is on (\(permissionText)). Next: try the fake test photos, then Test with 5."
            : "Photos access is off. Tap Open Settings → Photos → Full Access (or pick some photos)."
        await refresh()
    }

    func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url)
        }
    }

    // MARK: Actions

    func runTest() async {
        await perform(mode: .test(5), trigger: .app)
    }

    func runOrganizer(count: Int? = nil, trigger: RunTrigger = .app) async {
        await perform(mode: .next(count ?? batchSize), trigger: trigger)
    }

    private func perform(mode: RunMode, trigger: RunTrigger) async {
        await work("Working…") {
            let run = try await OrganizerEngine.shared.run(mode: mode, trigger: trigger) { text in
                Task { @MainActor in self.progress = text }
            }
            return ReportFormatter.runSentence(run)
        }
    }

    func makePreview() async {
        guard !busy else { return }
        busy = true
        progress = "Looking (no changes)…"
        preview = await OrganizerEngine.shared.preview(mode: .next(batchSize))
        message = preview.isEmpty
            ? "Nothing new to look at (or Photos access is off)."
            : "Here is what would happen to the next \(preview.count). Nothing was changed."
        progress = ""
        busy = false
    }

    func findDuplicates() async {
        await work("Looking for copies…") {
            try await OrganizerEngine.shared.collectDuplicates(scanLimit: 2000, trigger: .app).note
        }
    }

    func collectLongestVideos() async {
        await work("Finding your longest videos…") {
            try await OrganizerEngine.shared.collectLongestVideos(count: 15, trigger: .app).note
                + " They are in “\(ExtraAlbum.longestVideos)” for you to look at."
        }
    }

    func addTestPhotos() async {
        await work("Making fake test photos…") {
            let n = try await TestPhotoFactory.addSampleSet()
            return "Added \(n) FAKE test photos to “\(ExtraAlbum.testPhotos)”. Now tap Test with 5."
        }
    }

    func removeTestPhotos() async {
        await work("Removing fake test photos…") {
            let n = try await TestPhotoFactory.removeSampleSet(approved: true)
            return "Moved \(n) fake test photos to Recently Deleted. Real photos were not touched."
        }
    }

    func resetLog() async {
        await work("Clearing the log…") {
            try await OrganizerEngine.shared.ledger.reset()
            return "Log cleared. Albums in Photos were not changed. The next run will re-check items (anything already in an album is not added twice)."
        }
    }

    private func work(_ label: String, _ job: @escaping () async throws -> String) async {
        guard !busy else { return }
        busy = true
        progress = label
        do {
            message = try await job()
        } catch {
            message = error.localizedDescription
        }
        progress = ""
        busy = false
        await refresh()
    }
}
