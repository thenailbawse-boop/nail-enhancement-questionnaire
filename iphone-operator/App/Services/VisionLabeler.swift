import Foundation
import Photos
import UIKit
import Vision

/// On-device picture labels using Apple's Vision framework. A small thumbnail is made
/// on the phone, labeled on the phone, and thrown away. Nothing is uploaded.
/// iCloud-only originals are NOT downloaded (isNetworkAccessAllowed = false); those
/// items go to "Needs Review" instead of being guessed.
enum VisionLabeler {
    static func label(_ asset: PHAsset) -> (VisionStatus, [VisionLabel]) {
        guard asset.mediaType == .image else { return (.notAttempted, []) }

        let options = PHImageRequestOptions()
        options.isSynchronous = true
        options.isNetworkAccessAllowed = false
        options.deliveryMode = .highQualityFormat
        options.resizeMode = .fast

        let box = ValueBox<UIImage?>(nil)
        PHImageManager.default().requestImage(for: asset,
                                              targetSize: CGSize(width: 360, height: 360),
                                              contentMode: .aspectFit,
                                              options: options) { image, _ in
            box.value = image
        }
        guard let cgImage = box.value?.cgImage else { return (.imageUnavailable, []) }

        let request = VNClassifyImageRequest()
        do {
            try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])
            let observations = (request.results ?? [])
                .filter { $0.confidence >= 0.10 }
                .sorted { $0.confidence > $1.confidence }
                .prefix(8)
            return (.labeled, observations.map { VisionLabel(identifier: $0.identifier, confidence: Double($0.confidence)) })
        } catch {
            return (.failed, [])
        }
    }
}
