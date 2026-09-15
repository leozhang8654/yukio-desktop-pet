// swift-tools-version:5.9
import PackageDescription

// 雪绪桌面播放器。
// YukioCore：与平台无关的事件协议、活动路由、防抖、Claude 工具分类、转录解析、帧时间线。
// YukioPlayer：macOS 透明置顶窗口、拖动跑动、菜单栏、只读转录跟随。
let package = Package(
    name: "YukioPlayer",
    platforms: [.macOS(.v13)],
    targets: [
        .target(name: "YukioCore"),
        .executableTarget(name: "YukioPlayer", dependencies: ["YukioCore"]),
        .testTarget(name: "YukioCoreTests", dependencies: ["YukioCore"]),
    ]
)
