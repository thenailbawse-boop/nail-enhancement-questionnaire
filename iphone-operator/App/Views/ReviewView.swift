import SwiftUI

/// Shows what needs a human: "Needs Review", possible duplicates, and each review album.
struct ReviewView: View {
    @EnvironmentObject var model: OperatorModel
    @State private var selected = MediaCategory.needsReview.albumTitle
    @State private var ids: [String] = []

    private var albums: [String] {
        MediaCategory.allCases.map(\.albumTitle) + [ExtraAlbum.possibleDuplicates, ExtraAlbum.longestVideos, ExtraAlbum.testPhotos]
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Picker("Album", selection: $selected) {
                        ForEach(albums, id: \.self) { Text($0.replacingOccurrences(of: MediaCategory.albumPrefix, with: "")).tag($0) }
                    }
                    Text(help(for: selected)).font(.footnote).foregroundStyle(.secondary)
                }
                Section("Newest \(ids.count) in this album") {
                    if !model.canUsePhotos {
                        Text("Allow Photos on the Home tab first.")
                    } else if ids.isEmpty {
                        Text("Nothing here yet.").foregroundStyle(.secondary)
                    } else {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 86), spacing: 6)], spacing: 6) {
                            ForEach(ids, id: \.self) { AssetThumbnail(id: $0, side: 86) }
                        }
                        .padding(.vertical, 4)
                    }
                }
                Section {
                    Text("To change or delete something, open the Photos app → Albums → the “Reset ·” album. You decide; this app never deletes.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Review")
            .task(id: selected) { load() }
            .refreshable { load() }
        }
    }

    private func load() {
        ids = model.canUsePhotos ? PhotoLibrary.assetIDs(inAlbumTitled: selected, limit: 60) : []
    }

    private func help(for album: String) -> String {
        switch album {
        case MediaCategory.needsReview.albumTitle:
            return "The app wasn't sure about these, so it asks you instead of guessing. Some are iCloud-only photos it did not download."
        case ExtraAlbum.possibleDuplicates:
            return "Same size and same second as another item. Check them, then use Photos → Utilities → Duplicates to merge real copies."
        case ExtraAlbum.longestVideos:
            return "Long videos use the most space. Keep the ones you love; delete the rest yourself if you want space back."
        case MediaCategory.creatorContent.albumTitle:
            return "Your posting queue for the Instagram reset."
        case ExtraAlbum.testPhotos:
            return "Fake practice photos made by this app."
        default:
            return "Sorted by the organizer. Nothing was moved or copied — albums just point at your photos."
        }
    }
}
