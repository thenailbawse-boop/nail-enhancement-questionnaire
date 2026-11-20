import Foundation
#if canImport(FoundationModels)
import FoundationModels
#endif

/// Is Apple's free on-device model usable on THIS iPhone right now?
/// Needs iOS 26+, an Apple Intelligence–capable iPhone (iPhone 15 Pro or newer),
/// and Apple Intelligence turned on in Settings. Otherwise the app still works with its
/// rule-based brain; only the "Ask" chat and Safari AI planning are unavailable.
enum OnDeviceAIStatus {
    static var isAvailable: Bool {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            if case .available = SystemLanguageModel.default.availability { return true }
        }
        #endif
        return false
    }

    static var message: String {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, *) {
            let availability = SystemLanguageModel.default.availability
            if case .available = availability {
                return "On-device AI is ready. It runs on this iPhone — free, private, no account."
            }
            if case .unavailable(.deviceNotEligible) = availability {
                return "This iPhone model can't run Apple's on-device AI. Everything else still works."
            }
            if case .unavailable(.appleIntelligenceNotEnabled) = availability {
                return "Turn on Apple Intelligence in Settings → Apple Intelligence & Siri to use the AI helper."
            }
            if case .unavailable(.modelNotReady) = availability {
                return "Apple's AI is still downloading. Keep the phone on Wi-Fi and charging, then try later."
            }
            return "On-device AI isn't available right now."
        }
        #endif
        return "On-device AI needs iOS 26 or newer on an Apple Intelligence iPhone. Everything else still works."
    }
}
