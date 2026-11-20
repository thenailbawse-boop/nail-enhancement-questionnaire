import Foundation
import Photos
import UIKit

/// Photos permission, in plain words.
enum PhotoAccess {
    static var status: PHAuthorizationStatus { PHPhotoLibrary.authorizationStatus(for: .readWrite) }

    static var canUse: Bool { allowed(status) }

    static func allowed(_ status: PHAuthorizationStatus) -> Bool {
        status == .authorized || status == .limited
    }

    static func describe(_ status: PHAuthorizationStatus) -> String {
        switch status {
        case .authorized: return "Full access"
        case .limited: return "Only the photos you picked"
        case .denied: return "Turned off"
        case .restricted: return "Blocked by Screen Time or a work profile"
        case .notDetermined: return "Not asked yet"
        @unknown default: return "Unknown"
        }
    }

    static func request() async -> PHAuthorizationStatus {
        await PHPhotoLibrary.requestAuthorization(for: .readWrite)
    }
}

/// The only place the app touches the Photos library. Every change here is additive
/// (create an album, add an existing item to an album, add fake test photos) except
/// `deleteAppTestPhotos`, which only removes fake photos this app made and always
/// shows Apple's own "Delete?" confirmation.
enum PhotoLibrary {
    /// Newest photos and videos the app is allowed to see (hidden items are never included).
    static func newest(_ limit: Int, skipping skip: Set<String> = [], maxScan: Int = 50_000) -> [PHAsset] {
        guard limit > 0 else { return [] }
        let options = PHFetchOptions()
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        let result = PHAsset.fetchAssets(with: options)
        var picked: [PHAsset] = []
        var index = 0
        while index < result.count && picked.count < limit && index < maxScan {
            let asset = result.object(at: index)
            index += 1
            guard asset.mediaType == .image || asset.mediaType == .video else { continue }
            if skip.contains(asset.localIdentifier) { continue }
            picked.append(asset)
        }
        return picked
    }

    static func allVideos() -> [PHAsset] {
        let result = PHAsset.fetchAssets(with: .video, options: nil)
        var videos: [PHAsset] = []
        videos.reserveCapacity(result.count)
        result.enumerateObjects { asset, _, _ in videos.append(asset) }
        return videos
    }

    static func assets(ids: [String]) -> [PHAsset] {
        guard !ids.isEmpty else { return [] }
        let result = PHAsset.fetchAssets(withLocalIdentifiers: ids, options: nil)
        var assets: [PHAsset] = []
        result.enumerateObjects { asset, _, _ in assets.append(asset) }
        return assets
    }

    static func count(of type: PHAssetMediaType) -> Int {
        PHAsset.fetchAssets(with: type, options: nil).count
    }

    static func facts(for asset: PHAsset) -> MediaFacts {
        let kind: MediaKind
        switch asset.mediaType {
        case .image: kind = .photo
        case .video: kind = .video
        default: kind = .other
        }
        return MediaFacts(
            id: asset.localIdentifier,
            kind: kind,
            isScreenshot: asset.mediaSubtypes.contains(.photoScreenshot),
            hasDepthEffect: asset.mediaSubtypes.contains(.photoDepthEffect),
            isFavorite: asset.isFavorite,
            pixelWidth: asset.pixelWidth,
            pixelHeight: asset.pixelHeight,
            duration: asset.duration,
            creationDate: asset.creationDate
        )
    }

    // MARK: Albums

    static func findAlbum(titled title: String) -> PHAssetCollection? {
        if let id = AppSettings.albumIDs[title],
           let saved = PHAssetCollection.fetchAssetCollections(withLocalIdentifiers: [id], options: nil).firstObject {
            return saved
        }
        let result = PHAssetCollection.fetchAssetCollections(with: .album, subtype: .albumRegular, options: nil)
        var found: PHAssetCollection?
        result.enumerateObjects { collection, _, stop in
            if collection.localizedTitle == title {
                found = collection
                stop.pointee = true
            }
        }
        if let found { AppSettings.rememberAlbum(title, id: found.localIdentifier) }
        return found
    }

    /// Finds the album, or makes it once. Running again never makes a second copy.
    static func album(titled title: String) async throws -> PHAssetCollection {
        if let existing = findAlbum(titled: title) { return existing }
        let createdID = ValueBox<String?>(nil)
        try await PHPhotoLibrary.shared().performChanges {
            let request = PHAssetCollectionChangeRequest.creationRequestForAssetCollection(withTitle: title)
            createdID.value = request.placeholderForCreatedAssetCollection.localIdentifier
        }
        if let id = createdID.value,
           let created = PHAssetCollection.fetchAssetCollections(withLocalIdentifiers: [id], options: nil).firstObject {
            AppSettings.rememberAlbum(title, id: id)
            return created
        }
        if let found = findAlbum(titled: title) { return found }
        throw OperatorError.albumCreationFailed(title)
    }

    /// Which of `ids` are in the album right now. Used before (to skip) and after (to verify).
    static func members(of album: PHAssetCollection, among ids: [String]) -> Set<String> {
        let wanted = Set(ids)
        guard !wanted.isEmpty else { return [] }
        var present = Set<String>()
        PHAsset.fetchAssets(in: album, options: nil).enumerateObjects { asset, _, _ in
            if wanted.contains(asset.localIdentifier) { present.insert(asset.localIdentifier) }
        }
        return present
    }

    static func assetIDs(inAlbumTitled title: String, limit: Int) -> [String] {
        guard let album = findAlbum(titled: title) else { return [] }
        let options = PHFetchOptions()
        options.sortDescriptors = [NSSortDescriptor(key: "creationDate", ascending: false)]
        options.fetchLimit = limit
        var ids: [String] = []
        PHAsset.fetchAssets(in: album, options: options).enumerateObjects { asset, _, _ in ids.append(asset.localIdentifier) }
        return ids
    }

    static func itemCount(inAlbumTitled title: String) -> Int {
        guard let album = findAlbum(titled: title) else { return 0 }
        return PHAsset.fetchAssets(in: album, options: nil).count
    }

    /// Adds existing items to an album. Does not copy, edit or move the originals.
    static func add(_ assets: [PHAsset], to album: PHAssetCollection) async throws {
        guard !assets.isEmpty else { return }
        let list = assets as NSArray
        try await PHPhotoLibrary.shared().performChanges {
            PHAssetCollectionChangeRequest(for: album)?.addAssets(list)
        }
    }

    /// Removes ONLY fake test photos made by this app. iOS asks the person to confirm,
    /// and the photos go to Recently Deleted for 30 days.
    static func deleteAppTestPhotos(ids: [String]) async throws -> Int {
        let found = Self.assets(ids: ids)
        guard !found.isEmpty else { return 0 }
        let list = found as NSArray
        try await PHPhotoLibrary.shared().performChanges {
            PHAssetChangeRequest.deleteAssets(list)
        }
        return found.count
    }

    // MARK: Thumbnails (on-screen only)

    static func thumbnail(id: String, side: CGFloat) async -> UIImage? {
        guard let asset = Self.assets(ids: [id]).first else { return nil }
        let options = PHImageRequestOptions()
        options.deliveryMode = .highQualityFormat
        options.resizeMode = .fast
        options.isNetworkAccessAllowed = false
        options.isSynchronous = false
        return await withCheckedContinuation { continuation in
            let resumed = ValueBox(false)
            PHImageManager.default().requestImage(for: asset, targetSize: CGSize(width: side, height: side),
                                                  contentMode: .aspectFill, options: options) { image, _ in
                guard !resumed.value else { return }
                resumed.value = true
                continuation.resume(returning: image)
            }
        }
    }
}
