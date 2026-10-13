import AppKit
import ApplicationServices
import CryptoKit
import YukioCore

/// UI fallback for provider pages/panels that have no background request API.
/// Runs off the UI thread. It never clicks until an explicit card decision arrives.
final class SurfaceApprovalBridge {
    struct Candidate {
        let id: String
        let session: String
        let provider: String
        let question: PetQuestion
        let root: AXUIElement
        let buttons: [(String, AXUIElement)]
        let pid: pid_t
        let document: AXUIElement
        let address: String
    }
    private let queue = DispatchQueue(label: "yukio.surface-approvals")
    private var known: [String: Candidate] = [:]
    private var busy = false
    private var attempted = Set<String>()
    private var deadline = 0.0
    private var contentComplete = true
    private func value(_ node: AXUIElement, _ key: String) -> CFTypeRef? {
        var result: CFTypeRef?
        guard AXUIElementCopyAttributeValue(node, key as CFString, &result) == .success else { return nil }
        return result
    }
    private func label(_ node: AXUIElement) -> String {
        for key in [kAXTitleAttribute, kAXValueAttribute, kAXDescriptionAttribute] {
            if let text = value(node, key) as? String, !text.isEmpty { return text }
        }
        return ""
    }
    private func address(_ node: AXUIElement) -> String {
        if let url = value(node, kAXURLAttribute) as? URL { return url.absoluteString }
        return value(node, kAXURLAttribute) as? String ?? ""
    }
    private func children(_ node: AXUIElement) -> [AXUIElement] { value(node, kAXChildrenAttribute) as? [AXUIElement] ?? [] }
    private func content(_ root: AXUIElement) -> (String, [(String, AXUIElement)])? {
        contentComplete = true
        var stack = [(root, 0)], count = 0, texts: [String] = [], buttons: [(String, AXUIElement)] = []
        while let (node, depth) = stack.popLast() {
            count += 1
            guard count <= 160, depth <= 14, ProcessInfo.processInfo.systemUptime < deadline else { contentComplete = false; return nil }
            if value(node, "AXHidden") as? Bool == true { continue }
            let role = value(node, kAXRoleAttribute) as? String ?? ""
            if role == kAXButtonRole {
                let text = label(node)
                guard value(node, kAXEnabledAttribute) as? Bool != false else { continue }
                if ApprovalSurface.decision(text) != nil { buttons.append((text, node)) }
                continue
            }
            if [kAXTextFieldRole, kAXTextAreaRole, "AXLink", kAXMenuRole, kAXToolbarRole].contains(role) { continue }
            if role == kAXStaticTextRole { let text = label(node); if !text.isEmpty { texts.append(text) }; continue }
            stack.append(contentsOf: children(node).reversed().map { ($0, depth + 1) })
        }
        let text = texts.joined(separator: "\n")
        guard ApprovalSurface.isRequest(text: text, buttons: buttons.map(\.0)) else { return nil }
        return (text, buttons)
    }
    private func scan() -> [Candidate] {
        guard AXIsProcessTrusted() else { return [] }
        var found: [Candidate] = []
        deadline = ProcessInfo.processInfo.systemUptime + 2
        let apps = NSWorkspace.shared.runningApplications.filter { BrowserOpenChat.supportedBundles.contains($0.bundleIdentifier ?? "") }
        for app in apps {
            guard ProcessInfo.processInfo.systemUptime < deadline else { break }
            let ax = AXUIElementCreateApplication(app.processIdentifier)
            AXUIElementSetMessagingTimeout(ax, 0.1)
            let windows = value(ax, kAXWindowsAttribute) as? [AXUIElement] ?? []
            for window in windows where value(window, kAXMinimizedAttribute) as? Bool != true {
                var stack: [(AXUIElement, AXUIElement?, String, Int)] = [(window, nil, "", 0)]
                var visited = 0
                while let (node, inheritedDocument, inheritedURL, depth) = stack.popLast() {
                    visited += 1
                    guard visited <= 1800, depth < 35, ProcessInfo.processInfo.systemUptime < deadline else { break }
                    if value(node, "AXHidden") as? Bool == true { continue }
                    let role = value(node, kAXRoleAttribute) as? String ?? ""
                    var document = inheritedDocument, url = inheritedURL
                    if role == "AXWebArea" { document = node; url = address(node); if ApprovalSurface.provider(url: url) == nil { continue } }
                    if let document, let provider = ApprovalSurface.provider(url: url),
                       ["AXGroup", "AXDialog", "AXSheet"].contains(role), let (text, buttons) = content(node) {
                        // Choose the smallest qualifying container; parent matches would duplicate the same buttons.
                        if !children(node).contains(where: { content($0) != nil }) {
                            let identity = "\(app.processIdentifier):\(CFHash(window)):\(url):\(CFHash(node))"
                            let session = "surface-" + SHA256.hash(data: Data(identity.utf8)).map { String(format: "%02x", $0) }.joined()
                            let fullText = "\(app.localizedName ?? provider) · \(label(window))\n\(url)\n\n\(text)"
                            let hash = SHA256.hash(data: Data((identity + fullText + buttons.map(\.0).joined(separator: "\n")).utf8)).map { String(format: "%02x", $0) }.joined()
                            var q = PetQuestion(header: "\(provider.uppercased()) · 等你批准 / Approval", text: fullText,
                                options: buttons.map { .init(label: $0.0) })
                            q.approval = true
                            found.append(Candidate(id: "surface-approval:" + hash, session: session, provider: provider,
                                question: q, root: node, buttons: buttons, pid: app.processIdentifier, document: document, address: url))
                            continue
                        }
                    }
                    if ["AXLink", kAXMenuRole, kAXToolbarRole].contains(role) { continue }
                    stack.append(contentsOf: children(node).reversed().map { ($0, document, url, depth + 1) })
                }
            }
        }
        return found
    }
    func poll(enabled: Bool, providers: Set<String>, deliver: @escaping ([PetEvent]) -> Void) {
        guard !busy else { return }; busy = true
        queue.async {
            let candidates = enabled ? self.scan().filter { providers.contains($0.provider) } : []
            let next = Dictionary(candidates.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
            let now = Date().timeIntervalSince1970 * 1000
            var events: [PetEvent] = []
            func source(_ c: Candidate) -> String { c.provider == "gpt" ? "codex" : c.provider == "deepseek" ? "deepcode" : "claude-transcript" }
            for (id, c) in self.known where next[id] == nil {
                events.append(PetEvent(ts: now, source: source(c), session: c.session, kind: .activityEnd, eventID: id))
                self.attempted.remove(id)
            }
            for (id, c) in next where self.known[id] == nil && !self.attempted.contains(id) {
                events.append(PetEvent(ts: now, source: source(c), session: c.session, kind: .sessionTitle, detail: c.question.header))
                events.append(PetEvent(ts: now, source: source(c), session: c.session, kind: .activityStart, eventID: id,
                    activity: .question_for_user, tool: "Approval", detail: c.question.shortLabel, question: c.question))
            }
            self.known = next
            DispatchQueue.main.async { self.busy = false; deliver(events) }
        }
    }
    func send(session: String, callID: String, question: PetQuestion, answer: String) throws {
        try queue.sync {
            guard !attempted.contains(callID), let c = known[callID], c.session == session, c.question == question,
                  address(c.document) == c.address,
                  let current = scan().first(where: { $0.id == callID }), current.question == question,
                  let button = current.buttons.first(where: { $0.0 == answer }),
                  ApprovalSurface.decision(answer) != nil else { throw CodexAnswerClient.Failure.expired }
            // Once invoked, never replay an uncertain action automatically or on Retry.
            attempted.insert(callID)
            guard AXUIElementPerformAction(button.1, kAXPressAction as CFString) == .success else { throw CodexAnswerClient.Failure.rejected("press failed") }
            let deadline = Date().addingTimeInterval(2)
            while Date() < deadline {
                self.deadline = ProcessInfo.processInfo.systemUptime + 0.5
                if address(current.document) == current.address,
                   value(current.document, kAXRoleAttribute) as? String == "AXWebArea",
                   value(current.root, kAXRoleAttribute) != nil,
                   content(current.root) == nil, contentComplete { return }
                Thread.sleep(forTimeInterval: 0.1)
            }
            throw CodexAnswerClient.Failure.rejected("unconfirmed")
        }
    }
}

extension SurfaceApprovalBridge {
    private struct QuestionTarget {
        let root: AXUIElement
        let document: AXUIElement
        let url: String
        let field: AXUIElement
        let submit: AXUIElement
    }
    private func questionContent(_ root: AXUIElement, question: PetQuestion) -> (AXUIElement, AXUIElement)? {
        contentComplete = true
        var stack = [(root, 0)], texts: [String] = [], fields: [AXUIElement] = [], submits: [AXUIElement] = [], count = 0
        while let (node, depth) = stack.popLast() {
            count += 1
            guard count <= 100, depth < 15, ProcessInfo.processInfo.systemUptime < deadline else { contentComplete = false; return nil }
            if value(node, "AXHidden") as? Bool == true { continue }
            let role = value(node, kAXRoleAttribute) as? String ?? ""
            if [kAXTextFieldRole, kAXTextAreaRole].contains(role) {
                if value(node, kAXEnabledAttribute) as? Bool != false { fields.append(node) }
                continue
            }
            if role == kAXButtonRole {
                // Deliberately exclude ordinary chat-composer "Send" buttons.
                if ["submit", "submit answer", "send answer", "submit reply", "提交", "提交回答", "发送回答"].contains(label(node).lowercased()) { submits.append(node) }
                continue
            }
            if role == kAXStaticTextRole { texts.append(label(node)); continue }
            if ["AXLink", kAXMenuRole, kAXToolbarRole].contains(role) { continue }
            stack.append(contentsOf: children(node).reversed().map { ($0, depth + 1) })
        }
        let normalize: (String) -> String = { $0.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ") }
        let body = normalize(texts.joined(separator: " ")), wanted = normalize(question.text)
        guard wanted.count >= 12, body.contains(wanted), body.count < wanted.count + 600,
              fields.count == 1, submits.count == 1 else { return nil }
        return (fields[0], submits[0])
    }
    private func questionTargets(_ question: PetQuestion, provider: String, session: String, titles: [(id: String, title: String?)]) -> [QuestionTarget] {
        deadline = ProcessInfo.processInfo.systemUptime + 2
        var targets: [QuestionTarget] = []
        for app in NSWorkspace.shared.runningApplications where BrowserOpenChat.supportedBundles.contains(app.bundleIdentifier ?? "") {
            guard ProcessInfo.processInfo.systemUptime < deadline else { break }
            let root = AXUIElementCreateApplication(app.processIdentifier)
            AXUIElementSetMessagingTimeout(root, 0.1)
            for window in value(root, kAXWindowsAttribute) as? [AXUIElement] ?? [] where value(window, kAXMinimizedAttribute) as? Bool != true {
                var stack: [(AXUIElement, AXUIElement?, String, Int)] = [(window, nil, "", 0)], count = 0
                while let (node, inherited, oldURL, depth) = stack.popLast() {
                    count += 1
                    guard count < 1800, depth < 35, ProcessInfo.processInfo.systemUptime < deadline else { break }
                    if value(node, "AXHidden") as? Bool == true { continue }
                    let role = value(node, kAXRoleAttribute) as? String ?? ""
                    let doc = role == "AXWebArea" ? node : inherited
                    let url = role == "AXWebArea" ? address(node) : oldURL
                    if role == "AXWebArea" {
                        guard ApprovalSurface.provider(url: url) == provider else { continue }
                        if url.hasPrefix("chrome-extension://hehggadaopoacecdllhhajmbjkdcmajg/codex-sidepanel/") {
                            guard let header = BrowserOpenChat.selectedHeader(node, children: children,
                                role: { self.value($0, kAXRoleAttribute) as? String ?? "" }, label: label),
                                VisibleChatTitle.session(header: header, candidates: titles) == session else { continue }
                        } else {
                            guard VisibleChat(url: url)?.id == session else { continue }
                        }
                    }
                    if let doc, ApprovalSurface.provider(url: url) == provider, ["AXGroup", "AXDialog"].contains(role),
                       let (field, submit) = questionContent(node, question: question),
                       !children(node).contains(where: { questionContent($0, question: question) != nil }) {
                        targets.append(QuestionTarget(root: node, document: doc, url: url, field: field, submit: submit)); continue
                    }
                    if ["AXLink", kAXMenuRole, kAXToolbarRole].contains(role) { continue }
                    stack.append(contentsOf: children(node).reversed().map { ($0, doc, url, depth + 1) })
                }
            }
        }
        return targets
    }
    func sendQuestion(session: String, titles: [(id: String, title: String?)], callID: String, question: PetQuestion, answer: String, provider: String) throws {
        try queue.sync {
            guard !question.isApproval, !attempted.contains(callID), AXIsProcessTrusted() else { throw CodexAnswerClient.Failure.unavailable }
            let matches = questionTargets(question, provider: provider, session: session, titles: titles)
            guard matches.count == 1, let target = matches.first else { throw CodexAnswerClient.Failure.ambiguous }
            let draft = value(target.field, kAXValueAttribute) as? String ?? ""
            guard draft.isEmpty || draft == answer else { throw CodexAnswerClient.Failure.rejected("existing draft") }
            guard AXUIElementSetAttributeValue(target.field, kAXValueAttribute as CFString, answer as CFString) == .success else { throw CodexAnswerClient.Failure.unavailable }
            deadline = ProcessInfo.processInfo.systemUptime + 1
            guard address(target.document) == target.url,
                  questionContent(target.root, question: question) != nil,
                  value(target.field, kAXValueAttribute) as? String == answer,
                  value(target.submit, kAXEnabledAttribute) as? Bool != false else { throw CodexAnswerClient.Failure.expired }
            attempted.insert(callID)
            guard AXUIElementPerformAction(target.submit, kAXPressAction as CFString) == .success else { throw CodexAnswerClient.Failure.rejected("unconfirmed") }
            let until = Date().addingTimeInterval(2)
            while Date() < until {
                deadline = ProcessInfo.processInfo.systemUptime + 0.5
                if address(target.document) == target.url, value(target.root, kAXRoleAttribute) != nil, questionContent(target.root, question: question) == nil, contentComplete, ProcessInfo.processInfo.systemUptime < deadline { return }
                Thread.sleep(forTimeInterval: 0.1)
            }
            throw CodexAnswerClient.Failure.rejected("unconfirmed")
        }
    }
}
