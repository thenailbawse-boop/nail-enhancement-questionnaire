import SwiftUI
import Photos
import Vision
import AppIntents
import Combine

// iPhone Operator — prototype native execution layer.
// Set NSPhotoLibraryUsageDescription in the iOS app target's Info settings.
// The user must explicitly grant Photos read/write permission.
// No deletions, cloud uploads, Instagram automation, or hidden device control.

@main
struct iPhoneOperatorApp: App {
    @StateObject private var operatorModel = PhotoOperatorModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(operatorModel)
        }
    }
}

struct MediaCandidate: Identifiable {
    let id: String
    let category: String
    let kind: String
    let date: Date?
    let visionLabel: String
}

@MainActor
final class PhotoOperatorModel: ObservableObject {
    @Published var permission: String = "Not checked"
    @Published var message: String = "Grant Photos permission to begin."
    @Published var candidates: [MediaCandidate] = []
    @Published var busy = false

    func requestPermission() async {
        let status = await PHPhotoLibrary.requestAuthorization(for: .readWrite)
        permission = PhotoEngine.allowed(status) ? "Authorized" : "Not authorized"
        message = PhotoEngine.allowed(status)
            ? "Permission granted. Scan recent media to preview changes."
            : "Grant access in iOS Settings to use this feature."
    }

    func scan() {
        guard PhotoEngine.allowed(PHPhotoLibrary.authorizationStatus(for: .readWrite)) else {
            message = "Photos permission required."
            return
        }
        candidates = PhotoEngine.previewRecent(maxCount: 20)
        message = "Previewed \(candidates.count) assets. No changes were made."
    }

    func suggestNextSteps() async {
        guard !candidates.isEmpty else { message = "Scan recent media before requesting a plan."; return }
        if #available(iOS 26, *) {
            do {
                message = try await OnDevicePlanner.generateReadOnlyPlan(for: candidates)
            } catch {
                message = "On-device AI unavailable: \(error.localizedDescription). The safe sorting actions still work."
            }
        } else {
            message = "This AI planning option requires supported iOS 26+ Apple Intelligence hardware. Safe sorting remains available."
        }
    }

    func organize() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let count = try await PhotoEngine.organizeRecent(maxCount: 20)
            message = "Safely added \(count) new album memberships. Nothing was deleted or duplicated."
            scan()
        } catch {
            message = "Organization failed: \(error.localizedDescription)"
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var model: PhotoOperatorModel

    var body: some View {
        NavigationStack {
            List {
                Section("Permissions") {
                    LabeledContent("Photos", value: model.permission)
                    Button("Request Photos access") {
                        Task { await model.requestPermission() }
                    }
                }
                Section("Operator actions") {
                    Button("1. Inspect recent media") { model.scan() }
                    Button("2. Safely sort into review albums") {
                        Task { await model.organize() }
                    }
                    .disabled(model.busy)
                    Button("3. Generate optional on-device AI review plan") {
                        Task { await model.suggestNextSteps() }
                    }
                    Text("Sorts existing library items into Screenshots Review, Video Review, and Photo Review albums. Albums do not reduce device storage. No originals are changed or deleted.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Status") { Text(model.message) }
                Section("Recent media (local only)") {
                    ForEach(model.candidates) { item in
                        VStack(alignment: .leading, spacing: 3) {
                            HStack {
                                Text(item.category).font(.headline)
                                Spacer()
                                Text(item.kind).font(.caption)
                            }
                            if !item.visionLabel.isEmpty {
                                Text("On-device Vision: \(item.visionLabel)")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Text(item.date?.formatted(date: .abbreviated, time: .omitted) ?? "Unknown date")
                                .font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("iPhone Operator")
        }
    }
}

struct PhotoEngine {
    static let albums = ["Operator - Screenshots Review", "Operator - Video Review", "Operator - Photo Review"]

    static func allowed(_ authorization: PHAuthorizationStatus) -> Bool {
        authorization == .authorized || authorization == .limited
    }

    static func recentAssets(maxCount: Int) -> [PHAsset] {
        let options = PHFetchOptions()
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        options.fetchLimit = maxCount
        let result = PHAsset.fetchAssets(with: options)
        var assets: [PHAsset] = []
        result.enumerateObjects { asset, _, _ in assets.append(asset) }
        return assets
    }

    static func category(for asset: PHAsset) -> String {
        if asset.mediaSubtypes.contains(.photoScreenshot) { return albums[0] }
        if asset.mediaType == .video { return albums[1] }
        return albums[2]
    }

    static func previewRecent(maxCount: Int) -> [MediaCandidate] {
        // Vision labels are advisory only: never used to delete or transmit images.
        recentAssets(maxCount: maxCount).enumerated().map { index, asset in
            let label = index < 5 && asset.mediaType == .image ? visionLabel(for: asset) : ""
            return MediaCandidate(
                id: asset.localIdentifier,
                category: category(for: asset),
                kind: asset.mediaType == .video ? "Video" : "Photo",
                date: asset.creationDate,
                visionLabel: label
            )
        }
    }

    static func visionLabel(for asset: PHAsset) -> String {
        let opts = PHImageRequestOptions()
        opts.isSynchronous = true
        opts.isNetworkAccessAllowed = false
        opts.deliveryMode = .highQualityFormat
        var preview: UIImage?
        PHImageManager.default().requestImage(
            for: asset,
            targetSize: CGSize(width: 256, height: 256),
            contentMode: .aspectFit,
            options: opts
        ) { image, _ in preview = image }
        guard let cgImage = preview?.cgImage else { return "Local image unavailable" }
        let request = VNClassifyImageRequest()
        do {
            try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])
            guard let observation = request.results?.first, observation.confidence >= 0.65 else {
                return "Needs review"
            }
            return "\(observation.identifier) (\(Int(observation.confidence * 100))%)"
        } catch { return "Vision classification unavailable" }
    }

    static func album(named title: String) async throws -> PHAssetCollection {
        func lookup() -> PHAssetCollection? {
            let result = PHAssetCollection.fetchAssetCollections(with: .album, subtype: .albumRegular, options: nil)
            var found: PHAssetCollection?
            result.enumerateObjects { collection, _, stop in
                if collection.localizedTitle == title { found = collection; stop.pointee = true }
            }
            return found
        }
        if let existing = lookup() { return existing }
        try await PHPhotoLibrary.shared().performChanges {
            PHAssetCollectionChangeRequest.creationRequestForAssetCollection(withTitle: title)
        }
        guard let created = lookup() else { throw OperatorError.albumCreationFailed }
        return created
    }

    static func organizeRecent(maxCount: Int = 20) async throws -> Int {
        guard allowed(PHPhotoLibrary.authorizationStatus(for: .readWrite)) else {
            throw OperatorError.photosPermissionMissing
        }
        let assets = recentAssets(maxCount: maxCount)
        var additions = 0
        for albumTitle in albums {
            let group = assets.filter { category(for: $0) == albumTitle }
            guard !group.isEmpty else { continue }
            let destination = try await album(named: albumTitle)
            let albumAssets = PHAsset.fetchAssets(in: destination, options: nil)
            var existingIDs = Set<String>()
            albumAssets.enumerateObjects { asset, _, _ in existingIDs.insert(asset.localIdentifier) }
            let newAssets = group.filter { !existingIDs.contains($0.localIdentifier) }
            guard !newAssets.isEmpty else { continue }
            try await PHPhotoLibrary.shared().performChanges {
                PHAssetCollectionChangeRequest(for: destination)?.addAssets(newAssets as NSArray)
            }
            additions += newAssets.count
        }
        return additions
    }
}

enum OperatorError: Error, LocalizedError {
    case photosPermissionMissing
    case albumCreationFailed
    var errorDescription: String? {
        switch self {
        case .photosPermissionMissing: return "Photos permission has not been granted."
        case .albumCreationFailed: return "Couldn't create the requested Photos album."
        }
    }
}

// Apple's App Intents framework exposes actions to Shortcuts/Siri on supported iOS versions.
// It is not an authorization to control unrelated third-party app interfaces.
struct OrganizeCreatorMediaIntent: AppIntent {
    static var title: LocalizedStringResource = "Organize Recent Media"
    static var description = IntentDescription("Sorts up to twenty recent Photos assets into review albums without deleting files.")
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        guard PhotoEngine.allowed(PHPhotoLibrary.authorizationStatus(for: .readWrite)) else {
            return .result(dialog: "Open iPhone Operator and authorize Photos first.")
        }
        let count = try await PhotoEngine.organizeRecent(maxCount: 20)
        return .result(dialog: "Organized \(count) new album memberships. No deletions.")
    }
}

struct iPhoneOperatorShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: OrganizeCreatorMediaIntent(),
            phrases: ["Organize recent media with \(.applicationName)"],
            shortTitle: "Organize Media",
            systemImageName: "photo.on.rectangle"
        )
    }
}
