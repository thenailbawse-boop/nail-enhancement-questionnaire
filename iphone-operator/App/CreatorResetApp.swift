import SwiftUI

@main
struct CreatorResetApp: App {
    @StateObject private var model = OperatorModel()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        BackgroundOrganizer.register()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(model)
                .task {
                    #if DEBUG
                    await SelfTest.runIfRequested()
                    #endif
                    await model.refresh()
                }
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active:
                Task { await model.refresh() }
            case .background:
                BackgroundOrganizer.scheduleIfEnabled()
            default:
                break
            }
        }
    }
}

struct RootView: View {
    var body: some View {
        tabs
        #if DEBUG
            .overlay(alignment: .top) {
                if SelfTest.requested { SelfTestBanner() }
            }
        #endif
    }

    private var tabs: some View {
        TabView {
            HomeView()
                .tabItem { Label("Home", systemImage: "house") }
            ReviewView()
                .tabItem { Label("Review", systemImage: "rectangle.stack.badge.person.crop") }
            ResultsView()
                .tabItem { Label("Results", systemImage: "list.bullet.clipboard") }
            AskView()
                .tabItem { Label("Ask", systemImage: "sparkles") }
            HelpView()
                .tabItem { Label("Help", systemImage: "questionmark.circle") }
        }
    }
}

#if DEBUG
/// Only visible when launched with -CRSelfTest (automated checks). Never in Release builds.
struct SelfTestBanner: View {
    @ObservedObject private var status = SelfTestStatus.shared

    var body: some View {
        Text(status.text)
            .font(.caption2)
            .padding(6)
            .background(.yellow.opacity(0.9))
            .accessibilityIdentifier("selftest-status")
    }
}
#endif
