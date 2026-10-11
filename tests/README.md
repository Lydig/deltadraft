# Application checks

Run the automated checks from the repository root:

```powershell
node --test tests/milestone1.test.cjs tests/updates.test.cjs tests/update-install.test.cjs
```

These exercise both shipped renderer scripts, recommendation sharing, reference
data races and sample warnings, a simulated desktop draft, and the clipboard IPC
bridge. They do not establish that a real League client connects successfully.

The updater tests also check download/restart consent, failures, live-tracking
restart guards, IPC boundaries, isolated test identity and preferences, and the
local feed's artifact restrictions and byte-range responses. The feed test needs
loopback network access. See [desktop updates](../docs/desktop-updates.md) for the
safe UI preview and [the installation test](../docs/update-install-test.md) for the
real upgrade checklist. Neither automated tests nor the preview proves that an
installed update has succeeded.

## Test the desktop changes locally

From the repository root, launch the source version with:

```powershell
npm --prefix desktop-app start
```

An already-installed DraftDiff version will not include these source changes.

1. Open **How To Use**. Check the quick start, expandable explanation, keyboard
   navigation, and Escape to close.
2. Hover or focus the question marks. Clicking column help should not change the
   sort. Confirm that Lane remains visible separately from Enemy.
3. Change rank and time period. Both MID reference values should update. Raise
   Min Games above their sample counts: the raw reference values should remain
   visible, with low-sample warnings. Restore your preferred threshold afterward.
4. Suggest a role, then sort, search, and filter. **Copy top 10** should copy up to
   ten available champions in that displayed order, skipping greyed-out entries.
   Paste somewhere you can inspect the text before sending it.
5. In real League champion select, start live tracking. Check new picks, bans,
   hovers with the toggle on/off, teammate recommendations, and manual role locks.
   Stop and restart tracking and confirm the draft continues updating.

Also review the web version's manual drafting, help, reference, and clipboard
behavior. It retains the desktop download link and has no live tracking.

Creating a development checkpoint does not publish a release. Publishing requires
the owner's explicit approval after UI and real desktop live-tracking testing.
