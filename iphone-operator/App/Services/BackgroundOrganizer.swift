import BackgroundTasks
import Foundation

/// Asks iOS for quiet background time (usually overnight while charging) to organize the
/// next 50 items. iOS decides IF and WHEN this runs — it is not a guaranteed schedule and
/// it is not "always on". The Shortcuts automation is the more predictable option.
enum BackgroundOrganizer {
    /// Must match BGTaskSchedulerPermittedIdentifiers in App/Info.plist.
    static let taskID = "com.thenailbawse.creatorreset.organize"

    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskID, using: nil) { task in
            guard let processing = task as? BGProcessingTask else {
                task.setTaskCompleted(success: false)
                return
            }
            handle(processing)
        }
    }

    static func scheduleIfEnabled() {
        guard AppSettings.backgroundEnabled else {
            BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: taskID)
            return
        }
        let request = BGProcessingTaskRequest(identifier: taskID)
        request.requiresExternalPower = true
        request.requiresNetworkConnectivity = false
        request.earliestBeginDate = Date(timeIntervalSinceNow: 4 * 60 * 60)
        try? BGTaskScheduler.shared.submit(request)
    }

    private static func handle(_ task: BGProcessingTask) {
        scheduleIfEnabled() // ask for the next window too
        let work = Task {
            do {
                _ = try await OrganizerEngine.shared.run(mode: .next(50), trigger: .background)
                task.setTaskCompleted(success: true)
            } catch {
                task.setTaskCompleted(success: false)
            }
        }
        task.expirationHandler = { work.cancel() }
    }
}
