import Foundation

/// Finds *possible* duplicates using metadata only: same type, same size in pixels,
/// same capture second and same length. This catches saved-twice copies and re-imports.
/// It does NOT compare pixels, so results are "candidates for a human to check".
/// Real merging/deleting is left to Apple's own Photos → Utilities → Duplicates screen.
enum DuplicateFinder {
    struct Key: Hashable {
        let kind: MediaKind
        let width: Int
        let height: Int
        let second: Int64
        let tenthsOfSecond: Int
    }

    static func key(for facts: MediaFacts) -> Key? {
        guard let date = facts.creationDate, facts.pixelWidth > 0, facts.pixelHeight > 0 else { return nil }
        return Key(kind: facts.kind,
                   width: facts.pixelWidth,
                   height: facts.pixelHeight,
                   second: Int64(date.timeIntervalSince1970.rounded(.down)),
                   tenthsOfSecond: Int((facts.duration * 10).rounded()))
    }

    /// Groups of 2+ item IDs that look like copies of each other. Stable order (input order).
    static func candidateGroups(_ items: [MediaFacts]) -> [[String]] {
        var order: [Key] = []
        var groups: [Key: [String]] = [:]
        for item in items {
            guard let key = key(for: item) else { continue }
            if groups[key] == nil { order.append(key) }
            groups[key, default: []].append(item.id)
        }
        return order.compactMap { groups[$0] }.filter { $0.count >= 2 }
    }
}
