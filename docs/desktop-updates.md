# Desktop update notices

The desktop app checks the latest public GitHub release five seconds after launch.
The current version appears in small text beside **DraftDiff**; clicking it checks
again. If a newer stable release exists, an **Update available** button appears
beside the version. Its tooltip names the new version, and clicking it opens the
existing GitHub releases page for manual download and installation. Checking,
up-to-date and error messages appear briefly beneath the version without moving
the layout. Drafts, prereleases and invalid version tags are not offered.

The check works in the installed app and when running from source. It contacts
GitHub's public releases API without an account, token, or sending draft data.
There are no background installer downloads, install/restart controls, or links
between update notices and live-tracking logic. No new runtime dependency is needed.
The web app retains its existing desktop download link.

## Try it

From the repository root:

```powershell
npm --prefix desktop-app start
```

For a simulated newer release:

```powershell
npm --prefix desktop-app run start:update-preview
```

The yellow **Notice preview** label identifies this mode. It uses separate temporary
preferences, makes no release API request, and still opens the real download page
if that button is clicked. The flag is ignored in packaged apps.

Other preview states:

```powershell
npm --prefix desktop-app start -- --update-preview=up-to-date
npm --prefix desktop-app start -- --update-preview=error
```

Check that the version fits beside the title, clicking it checks again, and the
update button opens GitHub. Up-to-date and error messages clear after six seconds;
only an available update gets a button. Normal drafting/live tracking should
continue as before.

```powershell
node --test tests/milestone1.test.cjs tests/update-notice.test.cjs
```

## Scope and release decisions

The automatic-installer experiment remains saved on `codex/update-install-test`
at `9eaeb64`. It is deferred. Its GitHub build succeeded, but Windows Smart App
Control blocked the unsigned test installer on the owner's PC. A manual download
link does not remove that Windows installation restriction. No signing service
or new release infrastructure is part of this milestone.

The app version remains 4.5.1 until an approved release. This notice needs only an
ordinary published GitHub release tagged `vMAJOR.MINOR.PATCH`; it does not need
updater metadata, blockmaps or a private update server. Run local builds with
`npm --prefix desktop-app run dist`; `--publish never` prevents build-time publishing.
The owner tests changes before approving commits/releases and verifies live
tracking before release.

Keep work incremental. Check with the owner before expanding a milestone into
new services, accounts, paid tools, telemetry, or release infrastructure.
