# Actual installation test

This kit installs **DraftDiff Update Test 0.0.1**, then updates it through the app
to **0.0.2**. Both versions contain the current desktop source. They have a separate
Windows app identity, installation, updater cache, and preferences directory from
normal DraftDiff. The public app version and public GitHub update feed are unchanged.

The installers are unsigned, just like the existing DraftDiff installer. A hosted
build can finish packaging; it does not make an unsigned app trusted by Smart App
Control. If Windows blocks installation or restart, stop and report the exact
message. Do not turn off Windows protection. That result means signing or an
approved test machine is needed before this part of validation can finish.

## Build the kit

The GitHub workflow **Test desktop installation update** runs only on
pushes to `codex/update-install-test`, or a manual dispatch once GitHub has registered
the workflow. It uses a Windows runner, read-only repository permissions, no
repository secrets and no release publishing. A test-branch commit/push needs the
owner's approval. It does not merge into main, tag a version, or publish a release.

The workflow runs the tests, verifies a normal production package, then builds and
verifies the two isolated installers. Only the isolated kit is uploaded as an
Actions artifact, retained for seven days. In a public repository, signed-in users
with repository read access can download it; this is not private test hosting.

On an approved Windows build machine, the equivalent repository-root commands are:

```powershell
npm ci --prefix desktop-app --no-audit --no-fund
node --test tests/milestone1.test.cjs tests/updates.test.cjs tests/update-install.test.cjs
node tests/build-update-test.cjs
```

The builder refuses to overwrite an existing output. Supply a fresh directory as
the final argument if needed. Generated files stay under `workspace/` by default.
No production source files or version numbers are rewritten by this script.

## Test it step by step

1. In GitHub, open **Actions → Test desktop installation update → the successful
   run**. Under **Artifacts**, download **DraftDiff-update-install-test**. Extract
   the ZIP to a new folder. Keep `install`, `feed`, and `start-feed.cjs` together.
2. Open that extracted folder in File Explorer, type `powershell` in the address
   bar, and press Enter. Run:

   ```powershell
   node .\start-feed.cjs
   ```

   Leave this PowerShell window open. The feed listens only on this computer at
   `127.0.0.1:47831`. It does not require a firewall exception or router changes.
3. Open **install\DraftDiff-Update-Test-Setup-0.0.1.exe**. Install for your current
   user and keep the default **DraftDiff Update Test** destination. Do not choose
   the normal DraftDiff installation folder. If Windows blocks it, stop here.
4. Launch **DraftDiff Update Test**. Confirm the header identifies it as the test
   app and shows **v0.0.1**. Set a distinctive saved preference (for example a
   different rank/dataset), add a favorite, then close and reopen the app once to
   confirm those choices are saved. Existing normal-app favorites should not appear.
5. It should offer **0.0.2** within a few seconds. Click **Download update**. When
   ready, enable live tracking and confirm restart is disabled. Turn tracking off.
6. Click **Restart and install**, then **Cancel**. It should stay open with the
   update ready. Close and reopen the app: it must still be **0.0.1**, because
   quitting alone must not install an update. Click Download again if offered;
   the verified download may be reused from the cache.
7. Click **Restart and install** again and confirm. The real app should close,
   upgrade, and reopen at **v0.0.2**. It should report no newer version when checked.
   Confirm the saved rank/dataset and favorite remain. The current draft may reset.
8. In a real champion-select session, enable tracking and confirm picks and hovers
   sync. Check manual role movement and locks still work. This final check needs
   the owner; the simulated tests cannot prove a connection to the live client.
9. Close the test app and press **Ctrl+C** in the feed window when finished. Your
   normal DraftDiff installation should still have its original settings/version.
   The test app can be removed through Windows Installed apps under its separate name.

Report: starting version, resulting version, whether restart happened automatically,
whether preferences/favorites survived, and whether live tracking worked. Include
the exact Windows message if anything was blocked.

## Scope of the evidence

This checks real NSIS replacement, restart and persistence with the production
updater/controller/UI and live-tracking code. Only test branding, app identity,
preferences path, versions and feed configuration differ. The feed uses local HTTP
and single byte ranges; checksum verification remains enabled. It does not prove
GitHub release discovery, public HTTPS delivery, code-signing trust, or a migration
from today's updater-free 4.5.1. Those users need one manual installation of the
first approved updater-enabled release.
