import Foundation

/// Small saved settings. Stored only on this iPhone (UserDefaults). Safe to read from any thread.
enum AppSettings {
    private static let defaults = UserDefaults.standard

    private enum Key {
        static let paused = "operatorPaused"
        static let background = "backgroundEnabled"
        static let creatorKeywords = "creatorKeywords"
        static let testPhotoIDs = "testPhotoIDs"
        static let albumIDs = "albumIDs"
        static let firstFreeBytes = "firstFreeBytes"
        static let firstFreeDate = "firstFreeDate"
    }

    /// The owner's stop switch. When on, nothing changes in Photos — not from the app,
    /// not from Shortcuts, not from background time.
    static var isPaused: Bool {
        get { defaults.bool(forKey: Key.paused) }
        set { defaults.set(newValue, forKey: Key.paused) }
    }

    static var backgroundEnabled: Bool {
        get { defaults.bool(forKey: Key.background) }
        set { defaults.set(newValue, forKey: Key.background) }
    }

    static var defaultCreatorKeywordsText: String {
        ClassifierConfig.defaultCreatorKeywords.sorted().joined(separator: ", ")
    }

    static var creatorKeywordsText: String {
        get { defaults.string(forKey: Key.creatorKeywords) ?? defaultCreatorKeywordsText }
        set { defaults.set(newValue, forKey: Key.creatorKeywords) }
    }

    static var classifierConfig: ClassifierConfig {
        var config = ClassifierConfig.standard
        let custom = ClassifierConfig.parseKeywords(creatorKeywordsText)
        if !custom.isEmpty { config.creatorKeywords = custom }
        return config
    }

    /// IDs of the fake test photos this app created (the only items it may ever offer to remove).
    static var testPhotoIDs: [String] {
        get { defaults.stringArray(forKey: Key.testPhotoIDs) ?? [] }
        set { defaults.set(newValue, forKey: Key.testPhotoIDs) }
    }

    /// Album title → Photos album ID, so renamed or same-named albums don't confuse us.
    static var albumIDs: [String: String] {
        get { (defaults.dictionary(forKey: Key.albumIDs) as? [String: String]) ?? [:] }
        set { defaults.set(newValue, forKey: Key.albumIDs) }
    }

    static func rememberAlbum(_ title: String, id: String) {
        var ids = albumIDs
        ids[title] = id
        albumIDs = ids
    }

    /// The first free-space reading, so the owner can compare "before cleanup" with "now".
    static var firstFreeBytes: Int64? {
        get { defaults.object(forKey: Key.firstFreeBytes) as? Int64 }
        set { defaults.set(newValue, forKey: Key.firstFreeBytes) }
    }

    static var firstFreeDate: Date? {
        get { defaults.object(forKey: Key.firstFreeDate) as? Date }
        set { defaults.set(newValue, forKey: Key.firstFreeDate) }
    }
}

enum OperatorError: Error, LocalizedError {
    case photosPermissionMissing
    case paused
    case busy
    case albumCreationFailed(String)
    case blocked(String)

    var errorDescription: String? {
        switch self {
        case .photosPermissionMissing:
            return "Photos access is off. Open Creator Reset and tap Allow Photos."
        case .paused:
            return "The operator is paused. Turn off Pause in the app to let it make changes."
        case .busy:
            return "Already working on something. Try again in a moment."
        case .albumCreationFailed(let title):
            return "Couldn't make the album “\(title)”."
        case .blocked(let why):
            return why
        }
    }
}

/// A tiny box so PhotoKit callbacks can hand values back safely.
final class ValueBox<T>: @unchecked Sendable {
    var value: T
    init(_ value: T) { self.value = value }
}
