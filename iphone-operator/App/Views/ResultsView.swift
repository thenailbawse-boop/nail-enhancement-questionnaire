import SwiftUI

/// The action log: every run, and for each item what was true before and after.
struct ResultsView: View {
    @EnvironmentObject var model: OperatorModel
    @State private var confirmReset = false

    var body: some View {
        NavigationStack {
            List {
                if model.runs.isEmpty {
                    ContentUnavailableView("No runs yet", systemImage: "list.bullet.clipboard",
                                           description: Text("Tap Test with 5 photos on the Home tab."))
                }
                ForEach(model.runs) { run in
                    NavigationLink {
                        RunDetailView(run: run)
                    } label: {
                        VStack(alignment: .leading, spacing: 3) {
                            HStack {
                                Text(run.title).font(.headline)
                                Spacer()
                                Text(run.trigger.rawValue).font(.caption).foregroundStyle(.secondary)
                            }
                            Text(run.startedAt.formatted(date: .abbreviated, time: .shortened))
                                .font(.caption).foregroundStyle(.secondary)
                            Text("Added \(run.added) · already done \(run.alreadyOrganized) · review \(run.needsReview) · failed \(run.failed)")
                                .font(.caption)
                        }
                    }
                }
                if !model.runs.isEmpty {
                    Section {
                        ShareLink(item: model.ledgerURL) {
                            Label("Share the full log (no photos inside)", systemImage: "square.and.arrow.up")
                        }
                        Button("Clear the log", role: .destructive) { confirmReset = true }
                    }
                }
            }
            .navigationTitle("Results")
            .refreshable { await model.refresh() }
            .confirmationDialog("Clear the log?", isPresented: $confirmReset) {
                Button("Clear log", role: .destructive) { Task { await model.resetLog() } }
            } message: {
                Text("Your photos and albums stay exactly as they are.")
            }
        }
    }
}

struct RunDetailView: View {
    let run: RunSummary
    @State private var entries: [LedgerEntry] = []

    var body: some View {
        List {
            Section("Summary") {
                Text(ReportFormatter.runSentence(run))
                ForEach(ReportFormatter.categoryLines(run.perCategory), id: \.self) { Text($0) }
                LabeledContent("Free space before", value: ReportFormatter.bytes(run.freeBytesBefore))
                LabeledContent("Free space after", value: ReportFormatter.bytes(run.freeBytesAfter))
            }
            Section("Each item (\(entries.count))") {
                ForEach(entries) { entry in
                    HStack(alignment: .top, spacing: 10) {
                        AssetThumbnail(id: entry.assetID, side: 48)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(icon(entry.outcome)) \(entry.target.replacingOccurrences(of: MediaCategory.albumPrefix, with: ""))")
                                .font(.subheadline)
                            if !entry.reason.isEmpty { Text(entry.reason).font(.caption).foregroundStyle(.secondary) }
                            Text("Before: \(entry.before) → After: \(entry.after)").font(.caption2).foregroundStyle(.secondary)
                            if let error = entry.error { Text(error).font(.caption2).foregroundStyle(.red) }
                        }
                    }
                }
            }
        }
        .navigationTitle(run.title)
        .task { entries = await OrganizerEngine.shared.ledger.entries(for: run.id) }
    }

    private func icon(_ outcome: LedgerOutcome) -> String {
        switch outcome {
        case .done: return "✅"
        case .alreadyDone: return "↩️"
        case .skipped: return "⏭️"
        case .failed: return "⚠️"
        case .blocked: return "⛔️"
        }
    }
}
