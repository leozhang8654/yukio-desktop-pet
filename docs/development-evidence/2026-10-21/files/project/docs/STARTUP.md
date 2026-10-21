# 登录 Mac 时自动启动

打开桌宠设置，在“启动”区域切换“登录时自动启动”。开启后，登录当前 macOS 用户时自动打开雪绪；关闭后不再自动启动。首次添加功能不会替用户开启，已有系统设置会保留。

开关读取 macOS 登录项的实际状态，没有另存一份容易失步的布尔偏好。若系统要求批准，会显示提示和“打开系统登录项…”按钮；若修改失败，会显示错误并恢复系统实际状态。

使用 Apple 的 [`SMAppService.mainApp`](https://developer.apple.com/documentation/servicemanagement/smappservice/mainapp) 管理主 App 登录项，不添加 LaunchAgent 或额外后台程序。实现位于 `YukioPlayer/Sources/YukioPlayer/LaunchAtLogin.swift`，设置入口位于 `SettingsPanel.swift`。

验证覆盖开启、关闭、重复点击、待批准时取消、系统外部变更，以及注册/注销失败时不显示虚假成功。命令：

```sh
swift test --package-path YukioPlayer --filter LaunchAtLoginTests
```

登录项的真实开关需在安装好的 `.app` 中验证。编译生成的裸命令行程序不代表已安装 App 的注册状态。
