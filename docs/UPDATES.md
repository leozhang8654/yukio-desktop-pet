# In-app updates / 应用内更新

Starting with 0.4.0, Yukio checks for stable releases automatically. The update
window shows release notes and asks before downloading and restarting. Settings
includes a manual check button and an automatic-check switch. Checks use GitHub;
no account or token is needed and no local chat data is uploaded.

从 0.4.0 开始，雪绪自动检查正式版本并展示更新内容；用户点击后才下载、安装并重启。
设置里可以关闭自动检查，或随时手动检查。无更新及后台网络错误不弹窗。
Windows 点击稍后后，同一版本 24 小时内不再自动提醒；手动检查仍可立即查看。
Mac 的稍后/跳过及提醒调度由 Sparkle 管理。正常定期检查间隔为 6 小时。

## First installation

Versions before 0.4.0 cannot install updates themselves. Install 0.4.0 once:

- macOS: copy Yukio.app from the DMG into Applications, replacing the previous
  copy. Existing preferences use the same bundle identifier. Avoid running two
  different copies simultaneously.
- Windows: close the old standalone Yukio.exe, run `Yukio-0.4.0-Windows-Setup.exe`,
  then use the new shortcut. Installation is per user in `%LOCALAPPDATA%\YukioDesktop`.
  Settings remain in the existing application-data folder. The old standalone
  EXE is not deleted automatically because it may be in a user-selected folder.
  If login launch points to that old copy, enable login launch in the new app once.

后续更新无需删除旧版或访问下载页。首次安装仍可能出现系统信任提示；自动更新不等于
Apple 公证或 Windows Authenticode 签名。当前发布尚未配置这两种开发者证书。

## macOS release procedure

Sparkle 2.10.0 is pinned in Package.swift and Package.resolved. The package manager
verifies the vendor archive checksum. `build-app.sh` embeds the universal framework
with its signed nested services, adds the framework search path and the public
Ed25519 key. Both the feed and update archives require signatures. The private
key is in the releasing user's login Keychain under account `yukio-desktop-pet`;
never commit or publish it. Back it up securely before moving release machines.

1. Bump `CFBundleShortVersionString` and monotonically increase `CFBundleVersion`
   in `build-app.sh`. Add matching `docs/releases/<version>.md` notes.
2. Generate paging assets with `YukioWin/scripts/prepare-windows-assets.py`.
3. Run `YukioPlayer/scripts/package-release.sh`. It builds both CPU architectures,
   emits ZIP and DMG and generates/verifies signed `appcast.xml` using the Keychain.
4. Upload the ZIP, DMG, signed `appcast.xml`, Windows files and checksums to a draft
   GitHub Release on the verified commit. Publish only when every asset is present.
5. Verify the public `releases/latest/download/appcast.xml` endpoint and archive
   signatures. Do not modify a signed feed or archive after signing it.

The versioned ZIP is the update payload. The DMG is for first installation.
Automatic installation is disabled: users confirm each installation.

## Windows release procedure

Velopack Python and vpk are both pinned to 1.2.161. PyInstaller emits a directory,
which vpk turns into Setup, full update package, portable ZIP and release metadata.
`UpdateController` does network work on a daemon worker and dispatches results to
the Tk thread. Velopack verifies package hashes and replaces files after exit.
The source only includes stable GitHub releases; downgrades are not offered.

1. Bump `yukio.__version__` and add release notes.
2. Install dependencies and .NET 8, then `dotnet tool install -g vpk --version 1.2.161`.
3. Run `scripts/build-exe.ps1` from YukioWin. The CI workflow also builds an isolated
   0.3.99 baseline and performs a real install → update → restart test on Windows.
4. Publish the generated `releases.win.json`, full `.nupkg` and any associated
   assets unchanged, alongside the renamed user-facing Setup executable.
5. Preserve update package filenames in metadata. Do not upload just Setup: clients
   need the feed and the full package for their next update.

GitHub HTTPS and account/release controls protect Windows metadata transport;
package hashes detect corrupt downloads. This does not replace Authenticode.

## Testing

Run Swift tests and Python self-tests. Update-specific tests cover opt-out,
intervals, postponement, release notes, no-update/offline behaviour, repeated
clicks, downgrade refusal, download-before-restart, failed handoff and settings
preservation. Qualify actual packaged upgrades on both platforms before publishing.
Windows results must come from a Windows environment; local Python tests on macOS
are not a substitute. Keep previous installers and a backup of the installed Mac app.
