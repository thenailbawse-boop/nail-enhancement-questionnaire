import Foundation

// Pure data types shared by the iPhone app, the Safari extension and the unit tests.
// No Apple-only frameworks here, so this file also compiles and is tested on Linux.

enum MediaKind: String, Codable, Sendable {
    case photo
    case video
    case other
}

struct VisionLabel: Codable, Hashable, Sendable {
    var identifier: String
    var confidence: Double
}

/// Whether the on-device Vision step actually looked at a picture.
enum VisionStatus: String, Codable, Sendable {
    case labeled            // Vision ran on a local thumbnail
    case notAttempted       // e.g. videos: we do not claim to understand video content
    case imageUnavailable   // thumbnail not on this phone (often iCloud-only originals)
    case failed             // Vision returned an error
}

/// Everything the operator knows about one Photos item. Built from PhotoKit metadata
/// plus optional local Vision labels. Never contains pixels.
struct MediaFacts: Codable, Hashable, Sendable, Identifiable {
    var id: String
    var kind: MediaKind
    var isScreenshot: Bool = false
    var hasDepthEffect: Bool = false
    var isFavorite: Bool = false
    var pixelWidth: Int = 0
    var pixelHeight: Int = 0
    var duration: Double = 0
    var creationDate: Date?
    var visionStatus: VisionStatus = .notAttempted
    var labels: [VisionLabel] = []

    var isVertical: Bool { pixelHeight > 0 && Double(pixelHeight) >= Double(pixelWidth) * 1.5 }
}

/// The review albums the organizer files things into. One primary category per item.
enum MediaCategory: String, Codable, CaseIterable, Sendable {
    case screenshots
    case videos
    case creatorContent
    case personalPhotos
    case needsReview

    static let albumPrefix = "Reset · "

    var albumTitle: String { Self.albumPrefix + plainName }

    var plainName: String {
        switch self {
        case .screenshots: return "Screenshots"
        case .videos: return "Videos"
        case .creatorContent: return "Creator Content"
        case .personalPhotos: return "Personal Photos"
        case .needsReview: return "Needs Review"
        }
    }

    var systemImage: String {
        switch self {
        case .screenshots: return "camera.viewfinder"
        case .videos: return "video"
        case .creatorContent: return "sparkles"
        case .personalPhotos: return "heart"
        case .needsReview: return "questionmark.circle"
        }
    }
}

/// Extra review albums that are not a primary category.
enum ExtraAlbum {
    static let possibleDuplicates = MediaCategory.albumPrefix + "Possible Duplicates"
    static let longestVideos = MediaCategory.albumPrefix + "Longest Videos"
    static let testPhotos = MediaCategory.albumPrefix + "Test Photos (fake)"
}

struct ClassificationDecision: Codable, Hashable, Sendable {
    var category: MediaCategory
    var confidence: Double
    var reason: String
}
