# 0.4.0 update qualification

Status: implementation and isolated native upgrade testing complete; public release
and desktop replacement are gated on production update signing and public-download
verification. Do not interpret this report as confirmation of a published release.

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

- [Installed upgrade and regressions](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/37735245309): passed.
- [Missing feed, tampered package, installed upgrade and regressions](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/37735701914): passed.
- CI installs a packaged 0.3.99 baseline, discovers 0.4.0 with release notes,
  downloads, exits, replaces it, restarts, checks version and retained preferences.
- The latter run also rejects a missing feed and a deliberately modified update
  payload before performing the valid upgrade, then verifies there is no further update.
- Packaged named-pipe answering, compact settings/outside-click dismissal and
  native screenshots/animation-pixel comparisons at 100% and 150% pass.
- Current local Python suite: 248 tests, one platform-specific skip, all others pass.

## Release gate

Production `sign_update` is waiting for the user's macOS Keychain approval. The
computer-control tool refused access to SecurityAgent, so the authorization must
be completed by the user. An independent temporary test key allowed native upgrade
testing to finish without reading or bypassing the protected production key.

After authorization: sign/verify the final ZIP and appcast, merge the reviewed source,
prepare all GitHub release assets with checksums, verify public downloads, replace
and verify the user's running desktop app, and record the final source/package hashes.
The original desktop app remains 0.3.9 until this gate is completed.
