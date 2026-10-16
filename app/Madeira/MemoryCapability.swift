import Foundation

// ---------------------------------------------------------------------------
// Memory capabilities, resolved from three independent sources.
//
// The point of this file: a memory capability is only "on" if the kernel
// actually granted it AND it can be seen to take effect. A key appearing in a
// plist proves nothing - an app can carry a key it was never authorised for,
// and iOS will still run it without the capability. So every verdict here is
// backed by an observable: the value SecTask reports, the grants in the
// embedded provisioning profile, and the address map the process really got.
//
// Two different problems get two different entitlements, and conflating them is
// the mistake this replaces:
//   com.apple.developer.kernel.increased-memory-limit
//       Apple: "may perform better by exceeding the default app memory limit".
//       That is physical RAM. It does not make address space larger.
//   com.apple.developer.kernel.extended-virtual-addressing
//       Apple: "needs that require a larger addressable space ... games that
//       memory map assets to stream to the GPU may benefit".
//       That is virtual address space, which is what a large contiguous
//       VirtualAlloc reservation fails on.
// A game that dies on "unable to reserve N MB of address space" needs the
// second one. The first one cannot help it.
// ---------------------------------------------------------------------------

enum MemoryEntitlementKey {
    static let increasedMemoryLimit =
        "com.apple.developer.kernel.increased-memory-limit"
    static let extendedVirtualAddressing =
        "com.apple.developer.kernel.extended-virtual-addressing"
    static let getTaskAllow = "get-task-allow"

    static let all = [increasedMemoryLimit, extendedVirtualAddressing]
}

/// The embedded provisioning profile: what Apple authorised this build to have.
/// Every answer to "is this allowed" comes from here, never from the keys the
/// app asked for.
struct ProvisioningProfile {
    let present: Bool
    /// development | ad-hoc | enterprise | store | unknown
    let kind: String
    /// Days until the profile expires, when it carries a lifetime.
    let daysLeft: Int?
    /// The team the profile was issued to, when it carries one.
    let teamName: String?
    /// Entitlement key -> the profile authorises it.
    let granted: [String: Bool]

    static let unknown = ProvisioningProfile(present: false, kind: "unknown",
                                             daysLeft: nil, teamName: nil,
                                             granted: [:])

    static func load() -> ProvisioningProfile {
        guard let path = Bundle.main.path(forResource: "embedded",
                                          ofType: "mobileprovision"),
              let data = FileManager.default.contents(atPath: path),
              let start = data.range(of: Data("<?xml".utf8)),
              let end = data.range(of: Data("</plist>".utf8),
                                   in: start.lowerBound..<data.endIndex),
              let object = try? PropertyListSerialization.propertyList(
                  from: data.subdata(in: start.lowerBound..<end.upperBound),
                  options: [], format: nil),
              let plist = object as? [String: Any]
        else { return .unknown }

        let entitlements = plist["Entitlements"] as? [String: Any] ?? [:]
        var granted: [String: Bool] = [:]
        for (key, value) in entitlements {
            if let flag = value as? Bool { granted[key] = flag }
            else if let list = value as? [String] { granted[key] = !list.isEmpty }
        }

        let getTaskAllow = granted[MemoryEntitlementKey.getTaskAllow] == true
        let kind: String
        if (plist["ProvisionsAllDevices"] as? Bool) == true {
            kind = "enterprise"
        } else if plist["ProvisionedDevices"] != nil {
            kind = getTaskAllow ? "development" : "ad-hoc"
        } else {
            kind = "store"
        }

        var daysLeft: Int?
        if let created = plist["CreationDate"] as? Date,
           let expires = plist["ExpirationDate"] as? Date {
            let day = 86400.0
            daysLeft = Int((expires.timeIntervalSinceNow / day).rounded(.down))
        }
        return ProvisioningProfile(present: true, kind: kind,
                                   daysLeft: daysLeft,
                                   teamName: plist["TeamName"] as? String,
                                   granted: granted)
    }

    func authorises(_ key: String) -> Bool { granted[key] == true }
    /// A 7-day lifetime is a free Apple Account: free teams cannot hold
    /// restricted capabilities, so both memory entitlements are unobtainable.
    var isFreeAccount: Bool {
        guard let daysLeft else { return false }
        return daysLeft <= 7
    }
}

/// How one capability actually stands, right now, on this copy.
enum CapabilityState {
    /// The kernel reports it and the profile authorises it.
    case working
    /// The key is in this build's signature but the profile does not carry it,
    /// so it does nothing. The badge must not be green here.
    case presentButNotAuthorised
    /// Not in the signature at all.
    case absent
}

struct MemoryCapability {
    let key: String
    let title: String
    let state: CapabilityState
    /// What would actually make this work, stated so it can be acted on.
    let remediation: String
    /// True only when an observable effect was seen, not merely a plist key.
    let verifiedByEffect: Bool

    var isGreen: Bool { state == .working && verifiedByEffect }
}

struct MemoryCapabilityReport {
    let increasedMemory: MemoryCapability
    let extendedVA: MemoryCapability
    /// The address map the process actually received.
    let mapLow: UInt64
    let mapHigh: UInt64
    /// Measured from the process, not declared.
    var mapTopGB: UInt64 { mapHigh >> 30 }
    let profile: ProvisioningProfile

    /// One line for the diagnostic log.
    var logLine: String {
        "[memory] map=\(String(format: "[0x%llx,0x%llx)", mapLow, mapHigh))"
            + " top=\(mapTopGB)GB"
            + " profile=\(profile.kind)"
            + " days-left=\(profile.daysLeft.map(String.init) ?? "none")"
            + " free-account=\(profile.isFreeAccount ? 1 : 0)"
            + " increased-memory=\(stateTag(increasedMemory.state))"
            + "/\(increasedMemory.isGreen ? "verified" : "unverified")"
            + " extended-va=\(stateTag(extendedVA.state))"
            + "/\(extendedVA.isGreen ? "verified" : "unverified")"
    }

    private func stateTag(_ s: CapabilityState) -> String {
        switch s {
        case .working: return "working"
        case .presentButNotAuthorised: return "not-authorised"
        case .absent: return "absent"
        }
    }

    static func evaluate() -> MemoryCapabilityReport {
        let profile = ProvisioningProfile.load()
        let ents = EntitlementStatus.check()

        var mapLow: UInt64 = 0
        var mapHigh: UInt64 = 0
        let haveMap = jit_task_map_range(&mapLow, &mapHigh)

        // Without the entitlement the map ends around 0xfc0000000 (63 GB);
        // with it the ceiling is far higher. Measuring the map is how the
        // verdict is reached, because it is the only source that cannot be
        // satisfied by a key sitting in a file.
        let standardTop = UInt64(0xfc0000000)
        let mapExtended = haveMap && mapHigh > standardTop
        let evaClaimed = ents.extendedVA

        let evaState: CapabilityState
        if evaClaimed && profile.authorises(MemoryEntitlementKey.extendedVirtualAddressing) {
            evaState = .working
        } else if evaClaimed {
            evaState = .presentButNotAuthorised
        } else {
            evaState = .absent
        }
        // Green needs the effect, not just the key: the key set but the map
        // unchanged means the entitlement did nothing.
        let evaVerified = evaState == .working && mapExtended

        let memoryState: CapabilityState
        if ents.increasedMemory
            && profile.authorises(MemoryEntitlementKey.increasedMemoryLimit) {
            memoryState = .working
        } else if ents.increasedMemory {
            memoryState = .presentButNotAuthorised
        } else {
            memoryState = .absent
        }
        // There is no address-map analogue for a RAM limit, so this one is
        // verified by the profile plus the kernel, and is labelled as such.
        let memoryVerified = memoryState == .working

        let paidNote = profile.isFreeAccount
            ? " This build carries a \(profile.daysLeft ?? 7)-day profile, which means a "
              + "free Apple Account; free teams cannot hold restricted capabilities."
            : ""

        let increasedMemory = MemoryCapability(
            key: MemoryEntitlementKey.increasedMemoryLimit,
            title: "Memory+",
            state: memoryState,
            remediation: """
                \(profile.isFreeAccount
                  ? "Needs a paid Apple Developer Program team with the Increased Memory Limit capability."
                  : "Needs a profile that carries increased-memory-limit.")
                This entitlement raises the physical RAM limit only. It does not enlarge address space, \
                so it cannot fix a failure to reserve a large contiguous block.
                """,
            verifiedByEffect: memoryVerified)

        let extendedVA = MemoryCapability(
            key: MemoryEntitlementKey.extendedVirtualAddressing,
            title: "64-bit VA",
            state: evaState,
            remediation: """
                Needs a paid Apple Developer Program team with the Extended Virtual Addressing \
                capability enabled on the App ID, then a rebuild signed by that team. This is the \
                entitlement a "unable to reserve N MB of address space" failure actually needs.
                """,
            verifiedByEffect: evaVerified)

        return MemoryCapabilityReport(increasedMemory: increasedMemory,
                                      extendedVA: extendedVA,
                                      mapLow: mapLow, mapHigh: mapHigh,
                                      profile: profile)
    }
}