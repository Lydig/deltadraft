# Milestone 1 checks

Run the automated checks from the repository root:

```powershell
node --test tests/milestone1.test.cjs
```

These exercise both shipped renderer scripts, recommendation sharing, reference
data races and sample warnings, a simulated desktop draft, and the clipboard IPC
bridge. They do not establish that a real League client connects successfully.

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
