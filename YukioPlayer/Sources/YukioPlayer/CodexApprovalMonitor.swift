import Foundation
import YukioCore

/// All UI mutation stays on the main queue. Polls never submit decisions.
final class CodexApprovalMonitor {
    private var busy = false
    private var cursor = 0
    private var generation = 0
    private var shown: [String: [String: PetQuestion]] = [:]
    func poll(sessions: [String], enabled: Bool, deliver: @escaping ([PetEvent]) -> Void) {
        guard enabled, !sessions.isEmpty else {
            generation += 1
            let events = shown.flatMap { session, questions in questions.keys.map {
                PetEvent(ts: Date().timeIntervalSince1970 * 1000, source: "codex", session: session, kind: .activityEnd, eventID: $0)
            } }
            shown.removeAll(); deliver(events); return
        }
        guard !busy else { return }
        let currentGeneration = generation
        let session = sessions[cursor % sessions.count]; cursor += 1; busy = true
        DispatchQueue.global(qos: .utility).async {
            let result = Result { try CodexAnswerClient().pendingApprovals(session: session) }
            DispatchQueue.main.async {
                self.busy = false
                guard currentGeneration == self.generation else { return }
                let now = Date().timeIntervalSince1970 * 1000
                // Remove stale actionable cards on connection failure. Reconnection rediscovers them.
                let approvals = (try? result.get()) ?? []
                let next = Dictionary(approvals.map { ($0.callID, $0.question) }, uniquingKeysWith: { first, _ in first })
                let old = self.shown[session] ?? [:]
                var events = old.keys.filter { next[$0] == nil }.map {
                    PetEvent(ts: now, source: "codex", session: session, kind: .activityEnd, eventID: $0)
                }
                for (id, q) in next where old[id] == nil {
                    events.append(PetEvent(ts: now, source: "codex", session: session, kind: .activityStart,
                        eventID: id, activity: .question_for_user, tool: "Approval", detail: q.shortLabel, question: q))
                }
                self.shown[session] = next
                deliver(events)
            }
        }
    }
}
