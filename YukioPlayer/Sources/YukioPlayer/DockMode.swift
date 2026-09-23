import AppKit

/// 屏幕时间解锁模式：`YUKIO_DOCK=1` 启动时，雪绪临时开一扇普通窗口。
///
/// 起因：macOS「屏幕时间」若设了一刀切的限额（App 限额选「所有 App 与类别」，或停用期间），
/// 会拦下所有不在「始终允许」名单上的应用——按应用身份拦，跟用没用过、用了多久无关。
/// 被拦时雪绪的进程照样起来、照样烧 CPU，但窗口永远合成不出来：实测她的面板
/// `isOnActiveSpace=true`、`isVisible=true`，`occlusionState` 却始终是"完全被遮"，
/// 把窗口层级抬到 1000 也一样。看起来就是"双击了没反应、软件打不开"。
///
/// 而「始终允许」那张名单是按前台使用时长生成的，雪绪常驻后台、前台时长恒为 0，
/// 永远不会出现在里面，所以没法从名单里放行她。剩下的唯一入口是屏幕时间自己的遮罩
/// 对话框（「已达限额」+「请求更多时间」），可那个对话框只会盖在普通窗口上——
/// 雪绪平时只有一扇 `.nonactivatingPanel` 借位面板，勾不出对话框来。
///
/// 这个模式就是为了勾出那个对话框：把激活策略换成 `.regular` 并开一扇普通窗口，
/// 屏幕时间就会把遮罩盖上来，在上面点「请求更多时间」、输屏幕时间密码批准，
/// `local.yukio.player` 才算被放行。之后按平时的方式启动即可，别再带这个环境变量。
///
/// 注意：要在**普通桌面**上做，不能在别的 App 的全屏 Space 里——那里她抢不到前台，
/// 遮罩也就弹不出来。
enum DockMode {
    /// 开关只认环境变量，正常双击启动的雪绪不受任何影响。
    static var isEnabled: Bool {
        ProcessInfo.processInfo.environment["YUKIO_DOCK"] == "1"
    }

    private static var window: NSWindow?
    private static var observer: NSObjectProtocol?

    /// 在 `app.run()` 之前调用。没开开关就什么都不做。
    static func armIfEnabled() {
        guard isEnabled, observer == nil else { return }
        // 窗要等 App 起来之后再开，所以挂在启动通知上，不去动 AppController。
        observer = NotificationCenter.default.addObserver(
            forName: NSApplication.didFinishLaunchingNotification,
            object: nil,
            queue: .main
        ) { _ in present() }
    }

    private static func present() {
        guard window == nil else { return }
        let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 210),
                           styleMask: [.titled, .closable],
                           backing: .buffered,
                           defer: false)
        win.title = "雪绪 · 屏幕时间登记"
        win.isReleasedWhenClosed = false

        let label = NSTextField(wrappingLabelWithString: """
            这扇窗是用来勾出屏幕时间遮罩的。

            如果屏幕时间正在拦雪绪，稍等片刻就会弹出「已达限额」对话框，
            上面写着 local.yukio.player。点「请求更多时间」，输屏幕时间密码批准。

            批准之后关掉这扇窗，按平时的方式启动雪绪，不要再带 YUKIO_DOCK=1。
            """)
        label.font = .systemFont(ofSize: 13)
        label.translatesAutoresizingMaskIntoConstraints = false
        let content = win.contentView!
        content.addSubview(label)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 20),
            label.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -20),
            label.topAnchor.constraint(equalTo: content.topAnchor, constant: 20),
        ])

        win.center()
        win.makeKeyAndOrderFront(nil)
        // 只有真的抢到前台，屏幕时间才会记账。
        if #available(macOS 14.0, *) {
            NSApp.activate()
        } else {
            NSApp.activate(ignoringOtherApps: true)
        }
        window = win
    }
}
