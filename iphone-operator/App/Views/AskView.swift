import SwiftUI

/// Chat with Apple's on-device AI about the photo library. It can look and suggest;
/// changes only happen after the owner taps Approve.
struct AskView: View {
    @EnvironmentObject var model: OperatorModel
    @StateObject private var chat = AssistantChat()
    @State private var draft = ""

    private let examples = [
        "How is my photo library looking?",
        "What would you do with my next 20 photos?",
        "Do I have duplicates?",
        "Organize my next 50 items"
    ]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                List {
                    Section {
                        Label(chat.statusMessage, systemImage: chat.available ? "checkmark.seal" : "info.circle")
                            .font(.footnote)
                    }
                    if chat.lines.isEmpty {
                        Section("Try asking") {
                            ForEach(examples, id: \.self) { example in
                                Button(example) { Task { await chat.send(example) } }
                                    .disabled(!chat.available || chat.thinking)
                            }
                        }
                    }
                    ForEach(chat.lines) { line in
                        HStack {
                            if line.fromOwner { Spacer(minLength: 40) }
                            Text(line.text)
                                .padding(10)
                                .background(line.fromOwner ? Color.accentColor.opacity(0.18) : Color.secondary.opacity(0.12))
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            if !line.fromOwner { Spacer(minLength: 40) }
                        }
                        .listRowSeparator(.hidden)
                    }
                    if chat.thinking {
                        HStack { ProgressView(); Text("Thinking on this iPhone…").font(.footnote) }
                    }
                    if let count = chat.pendingCount {
                        Section("Needs your OK") {
                            Text("The AI wants to organize your next \(count) items into review albums. Nothing has changed yet.")
                            Button("Approve") { Task { await chat.approve(using: model) } }
                                .disabled(model.busy || model.isPaused)
                            Button("No thanks", role: .cancel) { Task { await chat.decline() } }
                        }
                    }
                }
                HStack {
                    TextField("Ask about your photos…", text: $draft, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(1...4)
                    Button {
                        let text = draft
                        draft = ""
                        Task { await chat.send(text) }
                    } label: {
                        Image(systemName: "arrow.up.circle.fill").font(.title2)
                    }
                    .disabled(!chat.available || chat.thinking || draft.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                .padding()
            }
            .navigationTitle("Ask")
        }
    }
}
