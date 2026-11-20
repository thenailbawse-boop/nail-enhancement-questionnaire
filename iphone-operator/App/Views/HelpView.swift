import SwiftUI
import UIKit

struct HelpView: View {
    @EnvironmentObject var model: OperatorModel
    @State private var copied = ""

    var body: some View {
        NavigationStack {
            List {
                Section("Keep it organized by itself") {
                    numbered([
                        "Open the Shortcuts app → Automation tab → + → Time of Day.",
                        "Pick a time (for example 2:00 AM), Daily, and choose “Run Immediately”.",
                        "Search for “Creator Reset” and pick “Organize Recent Media”. Set How many to 50.",
                        "Tap Done. Check Home → Last run the next morning."
                    ])
                    Text("If the phone is locked when it runs, iOS may stop it. If nothing ran, open the Results tab — it shows every run, including Shortcuts runs.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Toggle("Also ask iOS for overnight time while charging", isOn: $model.backgroundEnabled)
                    Text("iOS decides if and when this runs. It is a bonus, not a promise.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Free up space (you do these — the app never deletes)") {
                    numbered([
                        "Photos app → Albums → Utilities → Duplicates → Merge. Apple keeps the best copy.",
                        "Look in “Reset · Longest Videos”. Delete the ones you don't need.",
                        "Look in “Reset · Screenshots”. Delete old ones.",
                        "Photos → Albums → Recently Deleted → Select → Delete All. Space comes back only after this step.",
                        "Settings → General → iPhone Storage shows what else is big (apps, messages)."
                    ])
                    Text("Warning: if iCloud Photos is on, deleting here deletes on every device that uses the same Apple Account.")
                        .font(.footnote).foregroundStyle(.orange)
                }

                Section("Instagram reset") {
                    Text("What this app does: builds “Reset · Creator Content”, your posting queue. That's all. It cannot open, post to, archive or delete anything on Instagram — Instagram doesn't allow apps to do that.")
                        .font(.footnote)
                    numbered([
                        "Hide old posts yourself: Instagram → your post → ••• → Archive (you can un-archive later).",
                        "Pick new posts from “Reset · Creator Content”.",
                        "Use the buttons below to get help from AI apps you already use."
                    ])
                    Button("Copy: ChatGPT / Claude caption helper prompt") { copy(Prompts.captionHelper, "Caption prompt copied.") }
                    Button("Copy: Meta AI (Muse) account audit prompt") { copy(Prompts.museAudit, "Audit prompt copied.") }
                    Text("Status: what Meta AI / Muse can do with an Instagram account has NOT been tested yet. The prompt asks it to list what it can really do before doing anything.")
                        .font(.footnote).foregroundStyle(.secondary)
                    if !copied.isEmpty { Text(copied).font(.footnote).foregroundStyle(.green) }
                }

                Section("Safari helper") {
                    numbered([
                        "Settings → Apps → Safari → Extensions → Creator Reset → turn it on.",
                        "In Safari, open a normal website, tap the page menu (aA or the puzzle icon) → Creator Reset → Allow for this website.",
                        "Tap Inspect, type what you want, plan, read the steps, then Approve & run."
                    ])
                    Text("It works only on the tab you're looking at, only when you tap. It refuses sign-in pages, payments, posting, sending and deleting.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Privacy and how to stop") {
                    numbered([
                        "Pause: Home → Pause the operator. Nothing changes until you turn it off.",
                        "Take away Photos access: Settings → Apps → Creator Reset → Photos → None.",
                        "Stop the nightly run: Shortcuts → Automation → swipe left on it → Delete.",
                        "Remove everything: press and hold the app icon → Remove App. Your photos and albums stay."
                    ])
                    Text("Your photos never leave this iPhone. No account, no server, no ads. The log in Results stays on the phone unless you tap Share.")
                        .font(.footnote).foregroundStyle(.secondary)
                }

                Section("Not tested yet") {
                    Text("Built and checked by a computer, but not yet tried on a real iPhone: Shortcuts automations while locked, overnight background time, on-device AI answers, the Safari helper on a real iPhone, and Meta AI / Muse for Instagram.")
                        .font(.footnote)
                }

                Section {
                    LabeledContent("Version", value: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?")
                }
            }
            .navigationTitle("Help")
        }
    }

    private func numbered(_ steps: [String]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                HStack(alignment: .top, spacing: 8) {
                    Text("\(index + 1).").bold()
                    Text(step)
                }
                .font(.callout)
            }
        }
        .padding(.vertical, 2)
    }

    private func copy(_ text: String, _ note: String) {
        UIPasteboard.general.string = text
        copied = note
    }
}

enum Prompts {
    static let captionHelper = """
    You are my Instagram reset helper. I'm restarting my account as a creator.
    I'll describe photos from my posting queue (I will not upload private photos).
    For each one, give me: 1) a short caption in a friendly voice, 2) five hashtags, 3) the best day to post this week.
    Keep a steady theme across posts. Ask me 3 questions about my niche and audience first.
    """

    static let museAudit = """
    Before doing anything, tell me exactly what you can and cannot do with my connected Instagram account.
    Answer each with YES, NO or NOT SURE: read my old posts; read post stats; archive a post; delete a post; publish a post; edit a caption; run checks in the background.
    Do not change, archive, delete, publish or message anything. Only read.
    Then give me: a short audit of my account, a list of old posts I might want to archive (I'll archive them myself), and a weekly checklist to keep my account fresh.
    """
}
