# Desktop updates

DraftDiff uses `electron-updater` with the existing Windows NSIS installer and
public GitHub releases at `Lydig/deltadraft`. The web app is unchanged.

An installed Windows app checks five seconds after startup and every six hours.
The header also has a manual check. Stable releases only; no automatic downloads
or downgrades. Downloading, then restarting to install, require user actions.
Closing DraftDiff or shutting down Windows does **not** install a downloaded update.
Restart requires confirmation and is blocked while live tracking is enabled.
Failures offer retry and a button for the existing GitHub download page.

## Try the preview

From the repository root:

```powershell
npm --prefix desktop-app run start:update-preview
```

The yellow **Update preview** label identifies simulated updates. Click Download
update, wait for progress, then Restart and install. The confirmation simulates
success: nothing is downloaded, installed, or restarted. Preview preferences live
in the temporary `DraftDiff-update-preview` directory, separate from normal settings.
Preview mode cannot be enabled in a packaged app.

Other scenarios:

```powershell
npm --prefix desktop-app start -- --update-preview=up-to-date
npm --prefix desktop-app start -- --update-preview=error
npm --prefix desktop-app start -- --update-preview=download-error
```

Try canceling the restart confirmation. Also enable live tracking after the
simulated download: restart should be disabled until tracking is stopped. These
checks do not establish that picks and hovers sync in real champion select.

Normal `npm --prefix desktop-app start` uses real drafting but disables update
checks because it is running source code, not an installed app.

## Automated and packaging checks

```powershell
node --test tests/milestone1.test.cjs tests/updates.test.cjs
npm --prefix desktop-app run dist -- --config.directories.output=../workspace/update-verification
node tests/verify-update-package.cjs workspace/update-verification
```

The dist script always passes `--publish never`. Local builds do not upload files
or create releases. The example keeps build outputs in the ignored workspace.
The verifier checks packaged runtime files, the GitHub feed, manifest version,
installer filename, size and checksum, and presence of the blockmap.

## Before an approved release

The current source version stays at 4.5.1 until a release version is chosen.
A verification build with that version is **not** a new public release.

1. Complete the owner's UI and live-tracking checks and obtain release approval.
2. Choose a version newer than the current public release; update package.json
   and its lockfile, then build and verify the package.
3. Test an actual installed-version upgrade using isolated test installs and a
   local feed. Verify restart, settings/favorites preservation, cancel/failure
   behavior, and live tracking in the resulting app. The preview does not replace
   this test. Do not point public clients at test builds.
4. For the approved GitHub release, upload the generated installer, its `.blockmap`,
   and `latest.yml` **from the same build**, using the exact generated filenames.
   Do not rename files, hand-edit checksums, or mix build outputs. Publish only
   when the release and all assets are ready. Drafts and prereleases are not offered.

Current 4.5.1 installations contain no updater, so users need a manual installation
of the first updater-enabled release. Future upgrades can use the in-app controls.

The existing Windows installer is unsigned. This change does not add a signing
certificate or remove Windows prompts. It retains the updater's checksum and
code-signature verification behavior; enabling signed Windows releases is a
separate release-configuration decision.

References: [auto updates](https://www.electron.build/v26/docs/features/auto-update/)
and [publishing](https://www.electron.build/v26/docs/publish/).

## Local validation status (2026-10-11)

Automated checks and the native desktop preview cover detection, progress,
restart confirmation, and the live-tracking restart guard. A real installed
upgrade is still pending.

Final NSIS packaging is currently blocked on this workstation: Windows Code
Integrity rejects the unsigned temporary executable used to generate the
uninstaller (event 3077). A read-only policy check confirmed Smart App Control is
enabled and no current-user code-signing certificate was found. Resolve this
through an approved signing/build environment before release. The incomplete
installer outputs must not be distributed.

An [isolated installed-update test kit](update-install-test.md) and branch-only
GitHub Windows build workflow are prepared for the approved test branch. The kit
uses separate app identity, preferences, updater cache and a
loopback feed to test real NSIS upgrades from 0.0.1 to 0.0.2. A hosted build does not
resolve local trust in an unsigned installer; stop if Windows blocks the test.
All 25 automated checks pass. An unpacked test build at 0.0.2 was also built and
inspected: its identity/preferences are isolated, its updater/renderer/bridge
match the production source, and it contains no update simulation. The actual
installer and upgrade still need the hosted build and manual test.

Unpacked runtime verification can be performed independently:

```powershell
npm --prefix desktop-app run dist -- --dir --config.directories.output=../workspace/update-unpacked-verification
node tests/verify-update-package.cjs workspace/update-unpacked-verification --runtime-only
```
