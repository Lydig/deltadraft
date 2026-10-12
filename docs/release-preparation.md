# DraftDiff 4.6.0 release record

Status: [v4.6.0 was published](https://github.com/Lydig/deltadraft/releases/tag/v4.6.0)
on 2026-10-12 after the owner's approval. The public installer and checksum were
verified, and the production website serves the matching web source.

## Scope

The release includes tested checkpoints `f15ab61` and `8210502`: guidance and
tooltips, recommendation sharing, the collapsible directional counterpick reference,
and lightweight desktop update notices. Usage counts remain deferred.

The previous public release was `v4.5.1`. This release is `v4.6.0`, targeting build
commit `0ce9e641f3fc58c2dea0fc176568ecdaf266d7e5`. The package and lockfile agree on
`4.6.0`; the build icon points to the existing `desktop-app/build/icon.ico` file.

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

## Publication completed

- `main` was fast-forwarded to the approved release branch and pushed.
- GitHub release `v4.6.0` is public and marked latest. Its tag points to the exact
  build commit above. Uploaded assets are `DraftDiff.Setup.4.6.0.exe` and
  `SHA256SUMS.txt`; the checksum file uses the public installer's filename.
- The public installer download returns HTTP 200, and GitHub's asset digest and
  the public checksum file match the verified candidate's SHA-256 above.
- [The production website](https://deltadraft.vercel.app/) returns HTTP 200 and its
  HTML matches `web-app/index.html` after normalizing line endings. It includes
  COPY TOP 10, the collapsible reference, shared column help and the release link.
- The update controller, using the live public release response, reports
  `available` for a simulated 4.5.1 client and `up-to-date` for 4.6.0. Actual older
  installations do not contain this new controller; they must install 4.6.0
  manually to gain update notices.

The owner will download and test the published installer and website. The
incomplete local executable, automatic-updater experiment and analytics are not
part of the release.
