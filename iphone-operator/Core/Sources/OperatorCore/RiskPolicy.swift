import Foundation

/// Every action the operator knows about, with a fixed safety tier.
/// The AUTHORIZE step of the agent loop (observe → plan → authorize → execute → verify → log).
enum OperatorCapability: String, Codable, CaseIterable, Sendable {
    // Photos
    case scanLibrary
    case classifyOnDevice
    case createAlbum
    case addToAlbum
    case findDuplicates
    case storageReport
    case createTestPhotos
    case removeAppTestPhotos
    case deleteUserMedia
    case uploadMedia
    // Web (Safari extension)
    case webInspect
    case webScroll
    case webType
    case webClick
    case webSubmitForm
    case webEnterPassword
    case webPurchase
    // Instagram
    case instagramAudit
    case instagramArchive
    case instagramDelete
    case instagramPublish
}

enum RiskTier: String, Codable, Sendable, Comparable {
    case readOnly       // looks only
    case reversible     // easy to undo (e.g. remove from an album)
    case consequential  // needs a person to say yes every time
    case forbidden      // never done by this app

    private var rank: Int {
        switch self {
        case .readOnly: return 0
        case .reversible: return 1
        case .consequential: return 2
        case .forbidden: return 3
        }
    }
    static func < (lhs: RiskTier, rhs: RiskTier) -> Bool { lhs.rank < rhs.rank }
}

enum AuthorizationDecision: Equatable, Sendable {
    case allowed
    case needsApproval(String)
    case blocked(String)

    var isAllowed: Bool { self == .allowed }
}

enum RiskPolicy {
    static func tier(of capability: OperatorCapability) -> RiskTier {
        switch capability {
        case .scanLibrary, .classifyOnDevice, .findDuplicates, .storageReport, .webInspect, .instagramAudit:
            return .readOnly
        case .createAlbum, .addToAlbum, .createTestPhotos, .webScroll, .webType, .webClick:
            return .reversible
        case .removeAppTestPhotos:
            return .consequential
        case .deleteUserMedia, .uploadMedia, .webSubmitForm, .webEnterPassword, .webPurchase,
             .instagramArchive, .instagramDelete, .instagramPublish:
            return .forbidden
        }
    }

    /// - Parameters:
    ///   - paused: the owner's kill switch. When on, nothing but read-only work runs.
    ///   - approved: a person explicitly said yes to this specific action just now.
    static func authorize(_ capability: OperatorCapability, paused: Bool, approved: Bool) -> AuthorizationDecision {
        let tier = tier(of: capability)
        switch tier {
        case .forbidden:
            return .blocked("\(capability.rawValue) is turned off in this version for safety.")
        case .readOnly:
            return .allowed
        case .reversible:
            return paused ? .blocked("The operator is paused. Turn it back on in the app.") : .allowed
        case .consequential:
            if paused { return .blocked("The operator is paused. Turn it back on in the app.") }
            return approved ? .allowed : .needsApproval("This needs your OK each time.")
        }
    }
}
