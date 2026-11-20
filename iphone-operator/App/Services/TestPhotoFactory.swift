import Foundation
import Photos
import UIKit

/// Makes 12 obviously FAKE photos (colored cards with big "FAKE TEST PHOTO" text) so the
/// owner can try every button without touching real memories. Two of them are made as an
/// identical pair on purpose, so "Find possible duplicates" has something to find.
/// They are labeled, kept in their own album, and can be removed with one button.
enum TestPhotoFactory {
    struct Spec {
        let title: String
        let color: UIColor
        let size: CGSize
        let minutesAgo: Double
    }

    static let specs: [Spec] = [
        Spec(title: "Nail set close-up", color: .systemPink, size: CGSize(width: 1080, height: 1350), minutesAgo: 1),
        Spec(title: "Product flat-lay", color: .systemPurple, size: CGSize(width: 1080, height: 1080), minutesAgo: 2),
        Spec(title: "Reel cover", color: .systemIndigo, size: CGSize(width: 1080, height: 1920), minutesAgo: 3),
        Spec(title: "Copy A (duplicate pair)", color: .systemTeal, size: CGSize(width: 1200, height: 1600), minutesAgo: 4),
        Spec(title: "Copy B (duplicate pair)", color: .systemTeal, size: CGSize(width: 1200, height: 1600), minutesAgo: 4),
        Spec(title: "Landscape", color: .systemGreen, size: CGSize(width: 1920, height: 1080), minutesAgo: 5),
        Spec(title: "Quote graphic", color: .systemOrange, size: CGSize(width: 1080, height: 1080), minutesAgo: 6),
        Spec(title: "Before / after", color: .systemRed, size: CGSize(width: 1080, height: 1350), minutesAgo: 7),
        Spec(title: "Story slide", color: .systemBlue, size: CGSize(width: 1080, height: 1920), minutesAgo: 8),
        Spec(title: "Menu photo", color: .brown, size: CGSize(width: 1500, height: 1000), minutesAgo: 9),
        Spec(title: "Studio wall", color: .darkGray, size: CGSize(width: 1080, height: 1350), minutesAgo: 10),
        Spec(title: "Swatch card", color: .systemMint, size: CGSize(width: 1000, height: 1000), minutesAgo: 11)
    ]

    static func render(_ spec: Spec, number: Int) -> UIImage {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        return UIGraphicsImageRenderer(size: spec.size, format: format).image { context in
            spec.color.setFill()
            context.fill(CGRect(origin: .zero, size: spec.size))
            let paragraph = NSMutableParagraphStyle()
            paragraph.alignment = .center
            let attributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: spec.size.width / 11, weight: .heavy),
                .foregroundColor: UIColor.white,
                .paragraphStyle: paragraph
            ]
            let text = "FAKE TEST PHOTO\n#\(number)\n\(spec.title)" as NSString
            let box = CGRect(x: 40, y: spec.size.height * 0.28, width: spec.size.width - 80, height: spec.size.height * 0.6)
            text.draw(in: box, withAttributes: attributes)
        }
    }

    /// Adds the fake set to Photos inside "Reset · Test Photos (fake)". Returns how many were added.
    static func addSampleSet() async throws -> Int {
        guard PhotoAccess.canUse else { throw OperatorError.photosPermissionMissing }
        guard RiskPolicy.authorize(.createTestPhotos, paused: AppSettings.isPaused, approved: true).isAllowed else {
            throw OperatorError.paused
        }
        let album = try await PhotoLibrary.album(titled: ExtraAlbum.testPhotos)
        let now = Date()
        let prepared: [(UIImage, Date)] = specs.enumerated().map { index, spec in
            // Whole seconds so the duplicate pair truly shares a capture second.
            let date = Date(timeIntervalSince1970: (now.timeIntervalSince1970 - spec.minutesAgo * 60).rounded(.down))
            return (render(spec, number: index + 1), date)
        }
        let created = ValueBox<[String]>([])
        try await PHPhotoLibrary.shared().performChanges {
            var placeholders: [PHObjectPlaceholder] = []
            for (image, date) in prepared {
                let request = PHAssetChangeRequest.creationRequestForAsset(from: image)
                request.creationDate = date
                if let placeholder = request.placeholderForCreatedAsset {
                    placeholders.append(placeholder)
                    created.value.append(placeholder.localIdentifier)
                }
            }
            PHAssetCollectionChangeRequest(for: album)?.addAssets(placeholders as NSArray)
        }
        AppSettings.testPhotoIDs = AppSettings.testPhotoIDs + created.value
        return created.value.count
    }

    /// Removes only the fake photos listed in AppSettings.testPhotoIDs. iOS shows its own
    /// "Delete?" box first; if the person says no, nothing is removed.
    static func removeSampleSet(approved: Bool) async throws -> Int {
        switch RiskPolicy.authorize(.removeAppTestPhotos, paused: AppSettings.isPaused, approved: approved) {
        case .allowed: break
        case .needsApproval(let why), .blocked(let why): throw OperatorError.blocked(why)
        }
        let removed = try await PhotoLibrary.deleteAppTestPhotos(ids: AppSettings.testPhotoIDs)
        AppSettings.testPhotoIDs = []
        return removed
    }
}
