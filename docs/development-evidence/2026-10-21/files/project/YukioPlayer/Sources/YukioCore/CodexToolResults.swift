import Foundation
import CoreFoundation

/// Metadata-only result evidence. An output receipt is not proof of success;
/// a UI item identity is not automatically an outer tool-call identity.
/// This record is independent of the pet's display smoothing and end signals.
public struct CodexToolResult: Codable, Equatable, Sendable {
    public enum Outcome: String, Codable, Sendable { case succeeded, failed, cancelled, unknown }
    public let sessionID: String
    public let turnID: String?
    public let callID: String?
    public let itemID: String?
    public let sourceKind: String
    public let timestampMs: Double
    public let outcome: Outcome
    public let callOutcome: Outcome
    public let association: String
    public let exitCode: Int?
    public let projectionEligible: Bool
    public let conflictingResults: Bool
    public let turnAssociation: String
    public let itemType: String?
    public let reportedStatus: String?
    public var schemaVersion: Int = 1

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id", turnID = "turn_id", callID = "call_id", itemID = "item_id"
        case sourceKind = "source_kind", timestampMs = "timestamp_ms", outcome
        case callOutcome = "call_outcome", association, exitCode = "exit_code"
        case projectionEligible = "projection_eligible", conflictingResults = "conflicting_results"
        case schemaVersion = "schema_version"
        case itemType = "item_type", reportedStatus = "reported_status"
        case turnAssociation = "turn_association"
    }
}

/// Bounded per-parser correlation state; it is deliberately not a durable history.
final class CodexResultTracker {
    struct Checkpoint: Codable {
        struct Call: Codable { let id: String; let outcomes: [CodexToolResult.Outcome] }
        let turn_id: String?
        let closed: Bool
        let calls: [Call]
        let retired: [String]
    }

    func checkpoint() -> Checkpoint {
        Checkpoint(turn_id: turnID, closed: closed,
                   calls: order.map { Checkpoint.Call(id: $0, outcomes: (calls[$0] ?? []).sorted { $0.rawValue < $1.rawValue }) },
                   retired: retiredOrder)
    }

    func restore(_ state: Checkpoint) throws {
        guard state.calls.count <= capacity, state.retired.count <= capacity,
              Set(state.calls.map(\.id)).count == state.calls.count,
              Set(state.retired).count == state.retired.count else {
            throw CocoaError(.coderReadCorrupt)
        }
        turnID = state.turn_id; closed = state.closed
        order = state.calls.map(\.id)
        calls = Dictionary(uniqueKeysWithValues: state.calls.map { ($0.id, Set($0.outcomes)) })
        retiredOrder = state.retired; retired = Set(state.retired)
    }
    private(set) var turnID: String?
    private var closed = false
    private var calls: [String: Set<CodexToolResult.Outcome>] = [:]
    private var order: [String] = []
    private var retired: Set<String> = []
    private var retiredOrder: [String] = []
    private let capacity: Int

    init(capacity: Int = 4096) { self.capacity = capacity }

    static func identifier(_ value: Any?) -> String? {
        guard let s = value as? String, !s.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        return s
    }

    func reset() {
        calls.removeAll(); order.removeAll(); retired.removeAll(); retiredOrder.removeAll()
        turnID = nil; closed = false
    }
    func beginTurn(_ value: Any?) {
        if let turn = Self.identifier(value), turn != turnID || closed { retire(); closed = false; turnID = turn }
    }
    func closeTurn() { retire(); closed = true }
    private func retire() {
        for call in order where !retired.contains(call) {
            retired.insert(call); retiredOrder.append(call)
            if retiredOrder.count > capacity { retired.remove(retiredOrder.removeFirst()) }
        }
        calls.removeAll(); order.removeAll()
    }
    func isCurrent(_ value: Any?) -> Bool {
        let turn = Self.identifier(value)
        return !closed && (turn == nil || turn == turnID)
    }
    func matchesTurn(_ value: Any?) -> Bool {
        let turn = Self.identifier(value)
        return turn == nil || turnID == nil || turn == turnID
    }
    func start(_ value: Any?) {
        if closed { turnID = nil; closed = false } // Legacy records may omit turn boundaries.
        if let call = Self.identifier(value) { remember(call) }
    }
    private func remember(_ call: String) {
        guard calls[call] == nil else { return }
        calls[call] = []; order.append(call)
        if order.count > capacity { calls.removeValue(forKey: order.removeFirst()) }
    }

    static func outcome(_ obj: [String: Any]) -> (CodexToolResult.Outcome, Int?) {
        let status = (obj["status"] as? String)?.lowercased() ?? ""
        let metadata = obj["metadata"] as? [String: Any]
        let raw = obj["exit_code"] ?? metadata?["exit_code"]
        var code: Int?
        if let n = raw as? NSNumber, CFGetTypeID(n) != CFBooleanGetTypeID() {
            // Preserve exact JSON integers before converting through Double,
            // which rounds Int.max up to the first out-of-range integer.
            if let exact = Int(n.stringValue) { code = exact }
            else if n.doubleValue.isFinite, n.doubleValue.rounded() == n.doubleValue,
                    n.doubleValue >= Double(Int.min), n.doubleValue < Double(Int.max) { code = n.intValue }
        }
        func boolean(_ key: String, _ expected: Bool) -> Bool {
            guard let n = obj[key] as? NSNumber, CFGetTypeID(n) == CFBooleanGetTypeID() else { return false }
            return n.boolValue == expected
        }
        let result = obj["result"] as? [String: Any]
        func resultError(_ expected: Bool) -> Bool {
            guard let n = result?["isError"] as? NSNumber, CFGetTypeID(n) == CFBooleanGetTypeID() else { return false }
            return n.boolValue == expected
        }
        if ["cancelled", "canceled", "interrupted", "aborted"].contains(status) { return (.cancelled, code) }
        if ["failed", "error"].contains(status) || boolean("success", false) || boolean("isError", true) || resultError(true)
            || (code != nil && code != 0) { return (.failed, code) }
        // `completed` alone is a lifecycle receipt, not proof of tool success.
        if ["succeeded", "success"].contains(status) || boolean("success", true) || code == 0
            || boolean("isError", false) || resultError(false) {
            return (.succeeded, code)
        }
        return (.unknown, code)
    }

    func record(session: String, payload: [String: Any], item: [String: Any]? = nil,
                sourceKind: String, timestamp: Double) -> CodexToolResult {
        let obj = item ?? CodexRolloutParser.dictionary(payload["output"]) ?? [:]
        let itemID = item.flatMap { Self.identifier($0["id"]) }
        let explicitTurn = Self.identifier(payload["turn_id"])
        var turn = explicitTurn ?? turnID
        var turnAssociation = explicitTurn != nil ? "explicit_turn_id" : (turn != nil ? "current_context" : "unavailable")
        var call = Self.identifier((item ?? payload)["call_id"])
        if item != nil && call == nil { call = Self.identifier(payload["call_id"]) }
        var association = call == nil ? "unlinked" : "explicit_call_id"
        var current = isCurrent(turn)
        if call == nil && current {
            let candidate = item != nil ? itemID : Self.identifier(payload["id"])
            if let candidate, calls[candidate] != nil { call = candidate; association = "matching_item_id" }
        }
        if let call, retired.contains(call), explicitTurn == nil {
            // No turn ID: do not attach a potentially late result to a reused call.
            turn = nil; turnAssociation = "ambiguous_reused_call"; current = false
        }
        let (observed, code) = Self.outcome(obj)
        var resolved = CodexToolResult.Outcome.unknown
        var conflict = false
        if let call, current {
            remember(call)
            if observed != .unknown { calls[call, default: []].insert(observed) }
            let signals = calls[call] ?? []
            conflict = signals.count > 1
            resolved = signals.count == 1 ? signals.first! : .unknown
        }
        return CodexToolResult(sessionID: session, turnID: turn, callID: call, itemID: itemID,
                               sourceKind: sourceKind, timestampMs: timestamp, outcome: observed,
                               callOutcome: resolved, association: association, exitCode: code,
                               projectionEligible: call != nil && current, conflictingResults: conflict,
                               turnAssociation: turnAssociation,
                               itemType: item.flatMap { Self.identifier($0["type"]) },
                               reportedStatus: Self.identifier(obj["status"]))
    }
}
