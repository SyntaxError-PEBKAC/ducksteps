# ducksteps patch stack

These are the commits that turn a stock Firefox ESR checkout into ducksteps: exported with `git format-patch` from the `esr153` branch, applied on top of upstream Mozilla commit `861fdeb0d32f` (see [`../Docs/Building.md`](../Docs/Building.md) for the full build workflow).

To use them: clone [mozilla-firefox/firefox](https://github.com/mozilla-firefox/firefox), check out the matching ESR branch/tag, then apply in order:

```bash
git am --keep-cr Patches/0001-ducksteps-branding-patchset.patch Patches/0002-Custom-PGO-training-replace-Mozilla-default-workload.patch ... Patches/0022-ducksteps-track-build-files-that-were-never-committe.patch
```

or all at once:

```bash
git am --keep-cr Patches/*.patch
```

`--keep-cr` is required, not optional. Some of these patches touch files that are CRLF in the Firefox tree (`tools/upx-after-package.ps1`, the PGO extension sources), so their context and content lines carry carriage returns. `git am` strips trailing CRs by default, which corrupts those lines and makes the patch fail to apply.

Numbered in the order they were originally committed:

1. `ducksteps: branding + patchset`
2. `Custom PGO training: replace Mozilla default workload with realistic browsing corpus`
3. `ducksteps: WebExtension PGO training + profileserver patches`
4. `ducksteps: remove UPX from SFX stub (VT false positive fix)`
5. `Remove stale Marionette PGO script, superseded by background.js`
6. `ducksteps PGO: corpus updates — duckai behavior, speedtest fixes, dwell bumps`
7. `ducksteps PGO: fullscreen video, airbnb popup fix, librespeed retry, speedometer dwell bump, duck.ai submit fix`
8. `ducksteps PGO: remove video fullscreen, Speedometer dwell -15s, corpus tweaks`
9. `ducksteps: credit Mozilla and SyntaxError-PEBKAC in About dialog, point What's new to changelog`
10. `ducksteps: fix installer wizard bitmap artifacts`
11. `ducksteps: fix About dialog wordmark overlap on ESR 153`
12. `ducksteps: resync stub installer CSS with ESR 153 markup`
13. `ducksteps: telemetry prompts name Mozilla, not the maintainer`
14. `ducksteps: data reporting notice says "they", not "we"`
15. `ducksteps: correct the More from Mozilla settings page`
16. `ducksteps PGO: correct the corpus last-updated date`
17. `ducksteps: delete tools/upx-after-package.ps1`
18. `ducksteps PGO: drop old.reddit.com, fix LibreSpeed self-abort`
19. `ducksteps: enlarge and reposition the About dialog wordmark`
20. `ducksteps: replace the About dialog's flat purple with a space backdrop`
21. `ducksteps: fade the logo's edges instead of cutting it off square`
22. `ducksteps: track build files that were never committed`
