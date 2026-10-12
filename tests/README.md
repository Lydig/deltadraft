# Milestone 1 checks

Run the automated checks from the repository root:

```powershell
node --test tests/milestone1.test.cjs tests/update-notice.test.cjs
```

These exercise both shipped renderer scripts, recommendation sharing, reference
data races, sample warnings and saved expansion preferences, a simulated desktop draft, and the clipboard IPC
bridge. They do not establish that a real League client connects successfully.

The update-notice tests cover stable version comparison, network failures,
request isolation, renderer state and the fixed download-page link. See
[desktop updates](../docs/desktop-updates.md) for notice previews and scope.

## Test the desktop changes locally

From the repository root, launch the source version with:

```powershell
npm --prefix desktop-app start
```

An already-installed DraftDiff version will not include these source changes.

1. Open **How To Use**. Check the quick start, expandable explanation, keyboard
   navigation, and Escape to close.
2. Hover or focus the question marks. The single question mark after Role Freq
   explains all six metrics; clicking it should not change the sort.
3. Expand **High Delta 2 reference**, then reopen the app: it should stay expanded.
   Collapse and reopen: it should stay collapsed. New preferences start collapsed.
   Change rank and time period. Both MID reference values should update. Raise
   Min Games above their sample counts: the raw reference values should remain
   visible, with low-sample warnings. Restore your preferred threshold afterward.
4. Suggest a role, then sort, search, and filter. **COPY TOP 10** should copy up to
   ten available champions in that displayed order, skipping greyed-out entries.
   Paste somewhere you can inspect the text before sending it.
5. In real League champion select, start live tracking. Check new picks, bans,
   hovers with the toggle on/off, teammate recommendations, and manual role locks.
   Stop and restart tracking and confirm the draft continues updating.

Also review the web version's manual drafting, help, reference, and clipboard
behavior. It retains the desktop download link and has no live tracking.

Creating a development checkpoint does not publish a release. Publishing requires
the owner's explicit approval after UI and real desktop live-tracking testing.
