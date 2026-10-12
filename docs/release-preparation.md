# DraftDiff 4.6.0 release preparation

Status: GitHub Windows build succeeded and the downloaded installer was verified
on 2026-10-12. Awaiting approval to publish. No release or production deployment
has been made.

## Scope

The release includes tested checkpoints `f15ab61` and `8210502`: guidance and
tooltips, recommendation sharing, the collapsible directional counterpick reference,
and lightweight desktop update notices. Usage counts remain deferred.

The latest public release checked on 2026-10-12 was `v4.5.1`. Use `v4.6.0` for this
release. The local package and lockfile now agree on `4.6.0`; the build icon points
to the existing `desktop-app/build/icon.ico` file.

Public-facing release text is in [v4.6.0.md](releases/v4.6.0.md).

## Validation so far

- The owner approved the desktop UI and confirmed testing live tracking during an
  actual League champion select on 2026-10-12.
- All 21 draft and update-notice checks pass after changing the candidate version.
- The local packaged app has version 4.6.0. Runtime files, licenses and bundled
  assets match the source checkout.
- [GitHub build 38282395004](https://github.com/Lydig/deltadraft/actions/runs/38282395004)
  passed all 21 tests, built the installer and verified the packaged source,
  licenses and 182 assets against commit
  `0ce9e641f3fc58c2dea0fc176568ecdaf266d7e5`.
- The downloaded artifact matches GitHub's SHA-256 digest. The extracted installer
  matches its supplied checksum and reports version 4.6.0.
- The NSIS build stopped when Windows Code Integrity blocked execution of its
  temporary installer stub (event 3077). The file under
  `workspace/release-4.6.0/` was renamed with an `.incomplete` suffix and must not
  be distributed. No installer from this attempt is ready for use.

## Verified candidate

The workflow [build_desktop_candidate.yml](../.github/workflows/build_desktop_candidate.yml)
uses the same pinned GitHub actions and Windows runner as the earlier successful
installer test. It only runs tests, builds the ordinary NSIS installer, verifies
the packaged files, and uploads a review artifact. Its repository permissions are
read-only; the build explicitly disables publishing.

The owner approved committing and pushing the preparation to `codex/update-notice`.
That push started the successful build linked above. Its artifact
`DraftDiff-windows-x64-candidate` contains:

- `DraftDiff Setup 4.6.0.exe`
- `SHA256SUMS.txt` and `SOURCE.txt`, identifying the file and source commit
- `RELEASE-NOTES.md`

The verified local download is in
`workspace/release-4.6.0-github/candidate/`. The installer SHA-256 is
`b5de87c44cb613542bb88b26eac8e2817d9b1ddd20ddedf2150fb63b2c4b2812`.
This remains an unsigned installer: building on GitHub does not remove the Windows
installation restriction previously encountered on the owner's PC. It has not
been installed or run during this preparation.

## Publication is a separate step

After candidate review and explicit owner approval:

1. Incorporate the release branch into `main`, checking for intervening changes.
2. Publish the approved installer and release text as GitHub release `v4.6.0`,
   targeting the built commit `0ce9e641f3fc58c2dea0fc176568ecdaf266d7e5`.
3. Verify the web deployment for the updated `web-app/index.html` and its desktop
   download link. The repository contains Vercel configuration, but the deployment
   linkage and production branch still need confirmation before pushing `main`.
4. Verify the public download and update-notice behavior against the published
   release. Existing versions must install 4.6.0 manually to gain update notices.

Do not publish the incomplete local executable, the automatic-updater experiment,
or any new analytics as part of this release.
