import Foundation
import CryptoKit
import YukioCore

extension CodexAnswerClient {
    struct Approval {
        let callID: String
        let requestID: Any
        let method: String
        let params: [String: Any]
        let question: PetQuestion
    }
    static func approvals(snapshot: [String: Any], session: String) throws -> [Approval] {
        guard snapshot["id"] as? String == session else { throw Failure.protocolMismatch }
        let turns = try turns(in: snapshot)
        let live = turns.filter { $0["status"] as? String == "inProgress" }
        return try (snapshot["requests"] as? [[String: Any]] ?? []).compactMap { request in
            guard let method = request["method"] as? String,
                  ["item/commandExecution/requestApproval", "item/fileChange/requestApproval", "item/permissions/requestApproval"].contains(method),
                  let id = request["id"], let p = request["params"] as? [String: Any],
                  p["threadId"] as? String == session,
                  let turnID = p["turnId"] as? String, !turnID.isEmpty,
                  let turn = live.first(where: { $0["id"] as? String == turnID }),
                  request["completed"] as? Bool != true else { return nil }
            var details = p
            if method == "item/fileChange/requestApproval" {
                guard let item = (turn["items"] as? [[String: Any]])?.first(where: { $0["id"] as? String == p["itemId"] as? String }),
                      let changes = item["changes"] as? [[String: Any]], !changes.isEmpty else { return nil }
                details["changes"] = changes
            }
            let data = try JSONSerialization.data(withJSONObject: ["request": request, "details": details], options: [.sortedKeys, .withoutEscapingSlashes])
            guard data.count < 65536 else { return nil }
            let key = "codex-approval:" + SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
            let display = try JSONSerialization.data(withJSONObject: details, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
            var q = ApprovalQuestion.make(provider: "GPT", details: String(decoding: display, as: UTF8.self))
            if let decisions = p["availableDecisions"] as? [Any], !decisions.contains(where: { $0 as? String == "accept" }) {
                q = PetQuestion(header: q.header, text: q.text, options: [.init(label: ApprovalQuestion.deny)])
                q.approval = true
            }
            return Approval(callID: key, requestID: id, method: method, params: p, question: q)
        }
    }
    static func approvalSubmission(snapshot: [String: Any], session: String, callID: String,
                                   question: PetQuestion, answer: String) throws -> (method: String, params: [String: Any]) {
        let matches = try approvals(snapshot: snapshot, session: session).filter { $0.callID == callID && $0.question == question }
        guard matches.count == 1, let a = matches.first, a.question.options.contains(where: { $0.label == answer }),
              ApprovalQuestion.accepts(answer) else { throw Failure.expired }
        let allow = answer == ApprovalQuestion.allow
        var p: [String: Any] = ["conversationId": session, "requestId": a.requestID]
        if a.method == "item/permissions/requestApproval" {
            guard let permissions = a.params["permissions"] as? [String: Any] else { throw Failure.protocolMismatch }
            p["response"] = ["permissions": allow ? permissions : [:], "scope": "turn"]
            return ("thread-follower-permissions-request-approval-response", p)
        }
        p["decision"] = allow ? "accept" : "decline"
        return (a.method == "item/fileChange/requestApproval" ? "thread-follower-file-approval-decision" : "thread-follower-command-approval-decision", p)
    }
}
