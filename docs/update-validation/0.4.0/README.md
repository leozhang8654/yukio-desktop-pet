# 0.4.0 update qualification

Status: **released and verified**. [Yukio 0.4.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.0)
is public. Both platform packages and tag were built from
`5ffc426cfd2b9d00162ceb07d452266b4d58581b`. The user's desktop app is now 0.4.0.
See [release provenance](release-provenance.json) and [SHA-256 checksums](SHA256SUMS.txt).

## macOS

- 180 Swift tests pass, including update controls, visible settings layout and
  existing activity, animation, question and background-answer regressions.
- Packaged `--check` passes (13 animations). `--snapshot`, `--blink-snapshots` and
  `--settings-snapshot` were generated; the settings image was visually inspected.
- An isolated native app with its own bundle identifier and temporary trust root
  automatically discovered 0.4.0 from a signed localhost feed while on 0.3.99.
  The native release-notes window displayed the expected text.
- Remind Me Later kept the old app running. Manual Check then offered it again.
- One click on Install Update downloaded and replaced the bundle and automatically
  restarted it. The new native settings window showed 0.4.0, 135% and Chinese.
- Every regular file in the installed bundle matched the prepared target bundle.
- A subsequent check displayed “You're up to date”. An unsigned feed and an
  unavailable server were separately rejected while the old app remained usable.
- Production builds contain the production public key, require signed feeds and
  verify archive signatures before extraction. The test key is never shipped.
- Universal arm64/x86_64 ZIP and DMG are built. `codesign --verify --deep --strict`
  and `hdiutil verify` pass. This is ad-hoc app signing, not Developer ID notarization.

## Windows

Native GitHub Actions Windows runners were used. These are real Windows automated
results, not a claim of manual testing on a friend's PC.

- [Final 248-test run, upgrade and packaged regressions](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/37735984170): passed at source `035012bf7e47780d64afc0f2009ceb374a08467e`.
- [Installed upgrade and regressions](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/37735245309): passed.
- [Missing feed, tampered package, installed upgrade and regressions](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/37735701914): passed.
- CI installs a packaged 0.3.99 baseline, discovers 0.4.0 with release notes,
  downloads, exits, replaces it, restarts, checks version and retained preferences.
- The latter run also rejects a missing feed and a deliberately modified update
  payload before performing the valid upgrade, then verifies there is no further update.
- Packaged named-pipe answering, compact settings/outside-click dismissal and
  native screenshots/animation-pixel comparisons at 100% and 150% pass.
- Current local Python suite: 248 tests, one platform-specific skip, all others pass.

## Final delivery

- Production signing succeeded. Both archive and appcast signatures were verified
  independently against the public key embedded in the application.
- [Final same-source Windows build and upgrade](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38017080549)
  passed all 248 tests, tampered-package/missing-feed rejection, actual installed
  upgrade/restart/preferences checks and packaged native regressions.
- All ten public payload/metadata downloads matched their published checksums.
  The latest-release appcast matches the signed versioned feed.
- [Public Windows installer verification](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38017525626)
  downloaded and installed the published Setup, verified SHA-256 and version,
  passed matching-source tests, named-pipe answering, settings interactions and
  actual native rendering at 100%, 150% and 200%.
- The downloaded Mac ZIP, mounted DMG and installed desktop app match across all
  254 regular bundle files. The universal binary and nested signatures verify.
- The old desktop app was backed up before replacement. The actual desktop app
  runs 0.4.0 build 17, retains the original English/125% preferences and has automatic
  checks enabled. Its manual check against the production feed displayed
  “You're up to date” for 0.4.0.
- These builds still use ad-hoc macOS app signing and have no Windows Authenticode
  certificate. Initial operating-system trust prompts remain documented.

The earlier isolated-upgrade reports below document pre-release qualification;
the final publication source and hashes are in `release-provenance.json`.
