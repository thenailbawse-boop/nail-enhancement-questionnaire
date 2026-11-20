import SwiftUI

struct HomeView: View {
    @EnvironmentObject var model: OperatorModel
    @State private var confirmRemoveTests = false

    var body: some View {
        NavigationStack {
            List {
                statusSection
                permissionSection
                tryItSection
                organizeSection
                storageSection
                safetySection
                advancedSection
            }
            .navigationTitle("Creator Reset")
            .refreshable { await model.refresh() }
            .confirmationDialog("Remove the fake test photos?", isPresented: $confirmRemoveTests, titleVisibility: .visible) {
                Button("Remove \(model.testPhotoCount) fake photos", role: .destructive) {
                    Task { await model.removeTestPhotos() }
                }
            } message: {
                Text("Only the FAKE photos this app made are removed. iPhone will ask you once more. They stay in Recently Deleted for 30 days.")
            }
        }
    }

    private var statusSection: some View {
        Section {
            if model.busy {
                HStack(spacing: 10) {
                    ProgressView()
                    Text(model.progress.isEmpty ? "Working…" : model.progress)
                }
            }
            Text(model.message)
                .font(.callout)
            if model.isPaused {
                Label("Paused — nothing will be changed.", systemImage: "pause.circle.fill")
                    .foregroundStyle(.orange)
            }
        }
    }

    private var permissionSection: some View {
        Section("Step 1 · Allow Photos") {
            LabeledContent("Photos access", value: model.permissionText)
            if model.permission == .notDetermined {
                Button("Allow Photos") { Task { await model.requestAccess() } }
            } else if !model.canUsePhotos {
                Button("Open Settings") { model.openSettings() }
            } else {
                Button("Change which photos it can see") { model.openSettings() }
            }
            Text("The app only sees what you allow. It never deletes, edits or uploads your photos.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var tryItSection: some View {
        Section("Step 2 · Practice with fake photos (optional)") {
            Button("Add 12 fake test photos") { Task { await model.addTestPhotos() } }
                .disabled(!model.canUsePhotos || model.busy)
            if model.testPhotoCount > 0 {
                Button("Remove the fake test photos", role: .destructive) { confirmRemoveTests = true }
                    .disabled(model.busy)
            }
            Text("These are colored cards that say FAKE TEST PHOTO. Use them to see how it works before touching real memories.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var organizeSection: some View {
        Section("Step 3 · Organize") {
            Button {
                Task { await model.runTest() }
            } label: {
                Label("Test with 5 photos", systemImage: "5.circle")
            }
            .disabled(!model.canUsePhotos || model.busy)

            Picker("How many per run", selection: $model.batchSize) {
                Text("20").tag(20)
                Text("50").tag(50)
                Text("100").tag(100)
                Text("200").tag(200)
            }

            Button {
                Task { await model.runOrganizer() }
            } label: {
                Label("Run Organizer", systemImage: "wand.and.stars")
            }
            .disabled(!model.canUsePhotos || model.busy || model.isPaused)

            Button {
                Task { await model.makePreview() }
            } label: {
                Label("Preview only (change nothing)", systemImage: "eye")
            }
            .disabled(!model.canUsePhotos || model.busy)

            if !model.preview.isEmpty {
                NavigationLink("See preview (\(model.preview.count))") { PreviewListView(items: model.preview) }
            }

            if let last = model.lastRun {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Last run · \(last.trigger.rawValue)").font(.caption).foregroundStyle(.secondary)
                    Text(ReportFormatter.runSentence(last)).font(.footnote)
                }
            }
            Text("Albums appear in Photos → Albums, all starting with “Reset ·”. Running it again never adds the same photo twice.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var storageSection: some View {
        Section("Storage") {
            LabeledContent("Free space now", value: ReportFormatter.bytes(model.freeBytes))
            LabeledContent("Phone size", value: ReportFormatter.bytes(model.totalBytes))
            if let first = AppSettings.firstFreeBytes, let date = AppSettings.firstFreeDate {
                LabeledContent("Free on \(date.formatted(date: .abbreviated, time: .omitted))", value: ReportFormatter.bytes(first))
                Text(ReportFormatter.storageChange(before: first, after: model.freeBytes))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Button("Find possible duplicates") { Task { await model.findDuplicates() } }
                .disabled(!model.canUsePhotos || model.busy || model.isPaused)
            Button("Find my longest videos") { Task { await model.collectLongestVideos() } }
                .disabled(!model.canUsePhotos || model.busy || model.isPaused)
            Text("Organizing does NOT free space. Space is freed only when YOU delete things — see Help → Free up space.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var safetySection: some View {
        Section("Stop switch") {
            Toggle("Pause the operator", isOn: $model.isPaused)
            Text("When paused, nothing in Photos is changed — not by this screen, Shortcuts, Siri, or background time.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private var advancedSection: some View {
        Section("Advanced") {
            DisclosureGroup("Creator words") {
                TextField("Comma-separated words", text: $model.creatorKeywords, axis: .vertical)
                    .font(.footnote)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("Reset to default words") { model.creatorKeywords = AppSettings.defaultCreatorKeywordsText }
                Text("Photos whose on-device label matches one of these words go to Creator Content. Change them to fit the creator's niche.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }
}

struct PreviewListView: View {
    let items: [PreviewItem]

    var body: some View {
        List(items) { item in
            HStack(alignment: .top, spacing: 12) {
                AssetThumbnail(id: item.id, side: 64)
                VStack(alignment: .leading, spacing: 3) {
                    Label(item.decision.category.plainName, systemImage: item.decision.category.systemImage)
                        .font(.headline)
                    Text(item.decision.reason).font(.caption).foregroundStyle(.secondary)
                    if let date = item.facts.creationDate {
                        Text(date.formatted(date: .abbreviated, time: .shortened)).font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .navigationTitle("Preview (no changes)")
    }
}

struct AssetThumbnail: View {
    let id: String
    let side: CGFloat
    @State private var image: UIImage?

    var body: some View {
        ZStack {
            Rectangle().fill(.quaternary)
            if let image {
                Image(uiImage: image).resizable().scaledToFill()
            } else {
                Image(systemName: "photo").foregroundStyle(.secondary)
            }
        }
        .frame(width: side, height: side)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .task(id: id) {
            image = await PhotoLibrary.thumbnail(id: id, side: side * 2)
        }
    }
}
