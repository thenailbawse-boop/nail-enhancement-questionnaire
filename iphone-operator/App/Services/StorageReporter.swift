import Foundation

/// Reads the phone's free space the same way iOS does for "important" downloads.
/// Organizing into albums does NOT change this number. Only deleting things does.
enum StorageReporter {
    static func freeBytes() -> Int64? {
        let url = URL(fileURLWithPath: NSHomeDirectory())
        let values = try? url.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
        return values?.volumeAvailableCapacityForImportantUsage
    }

    static func totalBytes() -> Int64? {
        let url = URL(fileURLWithPath: NSHomeDirectory())
        let values = try? url.resourceValues(forKeys: [.volumeTotalCapacityKey])
        return values?.volumeTotalCapacity.map(Int64.init)
    }

    /// Saves the very first reading so "before" vs "now" can be shown later.
    static func rememberFirstReadingIfNeeded() {
        guard AppSettings.firstFreeBytes == nil, let free = freeBytes() else { return }
        AppSettings.firstFreeBytes = free
        AppSettings.firstFreeDate = Date()
    }
}
