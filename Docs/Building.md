# ducksteps Build & Release Runbook

**Environment:**
- MozillaBuild shell: `D:\mozilla-build\start-shell.bat`
- Source: `D:\mozilla-source\ducksteps`
- Objdir: `D:\ducksteps-obj\esr1XX`
- Legacy Objdir: `D:\ducksteps-obj\esr1XX-Legacy`
- rcedit: `C:\Users\User\.mozbuild\rcedit\rcedit-x64.exe`
- package.sh: `D:\mozilla-source\ducksteps\package.sh`

---

## 🖥️ Step 1 — Open the build shell

Run `start-shell.bat` from `D:\mozilla-build`.

---

## 📂 Step 2 — Navigate to source

```bash
cd /d/mozilla-source/ducksteps
```

---

## 🔄 Step 3 — Fetch latest tags from upstream

```bash
git fetch --tags origin
```

---

## 🏷️ Step 4 — Find the new release tag

```bash
git tag -l "FIREFOX_1XX*esr*RELEASE"
```

You're looking for a tag in the format `FIREFOX_1XX_X_0esr_RELEASE` where X is the new point release.

If the tag isn't listed, the release hasn't been tagged upstream yet. Do not proceed until it appears.

---

## 🌿 Step 5 — Switch to your local branch

```bash
git checkout esr1XX
```

Expected output includes:

```
Switched to branch 'esr1XX'
Your branch and 'origin/esr1XX' have diverged...
```

This is normal. Do **not** run `git pull` — it will destroy your local patchset on a diverged branch.

---

## 🔀 Step 6 — Rebase your patchset onto the new release tag

Replace `FIREFOX_1XX_X_0esr_RELEASE` with the actual tag from Step 4.

```bash
git rebase FIREFOX_1XX_X_0esr_RELEASE
```

If you hit a conflict, git pauses and tells you which file. Resolve it, then:

```bash
git rebase --continue
```

---

## ✅ Step 7 — Verify the version

```bash
cat browser/config/version.txt
cat browser/config/version_display.txt
```

Expected output:

```
1XX.X.X
1XX.X.Xesr
```

If either file shows the old version number, stop. The rebase didn't land correctly.

---

## 🧹 Step 8 — Clobber

```bash
./ mach clobber
```

Safe default for all release builds. Avoids stale outputs from the previous build.

---

## 🔨 Step 9 — Build & Test

```bash
./mach build
```

This will take a long time. The PGO flow runs automatically:

1. Instrumented build compiles
2. Firefox launches silently to collect profile data — **do not interrupt this**
3. Optimized build compiles using profile data

Build is complete when you see:

```
your build finally finished successfully!
```

Next test the browser built successfully by running:

```bash
./mach run
```

Do not distribute anything from the `instrumented/` folder in the objdir — that's the PGO training binary, not the final build.

---

## 📦 Step 10 — Package (icon stamp + assembly)

```bash
./package.sh
```

This does two things in order:

1. Stamps the ducksteps icon onto the NSIS stub via `rcedit-x64.exe` **before** mach package runs. (rcedit truncates anything past the PE boundary — running it post-assembly destroys the installer.)
2. Calls `./ mach package`, which appends the 7z payload to the already-stamped stub.

**Sanity check:** The installer EXE should be approximately 72 MB. If it's under 1 MB, the icon stamping corrupted it — re-run `./package.sh`.

Raw outputs after this step:

| File | Path |
|---|---|
| Installer EXE | `D:/ducksteps-obj/esr1XX/dist/install/sea/firefox-1XX.X.X.en-US.win64.installer.exe` |
| Standalone ZIP | `D:/ducksteps-obj/esr1XX/dist/firefox-1XX.X.X.en-US.win64.zip` |

---

## 🗜️ Step 11 — Verify UPX ran

UPX compression on the 7-zip SFX stub runs automatically during `./ mach package`.
Confirm it ran cleanly:

```bash
upx -t /d/ducksteps-obj/esr1XX/dist/install/sea/firefox-*.win64.installer.exe
```

Expected output: `[OK]`. If it fails, re-run `./package.sh`.

**Post-rebase patch — exe_7z_archive.py UPX flags:**
File: `python/mozbuild/mozbuild/action/exe_7z_archive.py`
Remove `--best`, `--lzma`, `--ultra-brute` from the UPX cmd list. Replace with `-6` only.
Without this, UPX 5.x triggers 4-6 VirusTotal flags on Setup.exe.

---

## 7️⃣ Step 12 — Repack standalone as 7z

Convert the ZIP from Step 10 to a 7z using these exact settings:

- Format: 7z
- Compression level: 9 — Ultra
- Method: LZMA2
- Dictionary size: 3840 MB
- Word size: 273
- Solid block: yes
- Threads: 3

Output filename: `ducksteps.1XX.X.X.Standalone.7z`

---

## #️⃣ Step 13 — Checksum both release files

In PowerShell:

```powershell
Get-FileHash "ducksteps.1XX.X.X.Setup.exe" -Algorithm SHA256
Get-FileHash "ducksteps.1XX.X.X.Standalone.7z" -Algorithm SHA256
```

Submit both to [VirusTotal](https://www.virustotal.com). Save the result URLs — they go in the release notes.

Expected false positive pattern: Arctic Wolf and/or Jiangmin flagging Setup.exe due to UPX compression heuristics. Anything beyond those two warrants investigation.

---

## 🚀 Step 14 — Publish on GitHub

1. Repo → **Releases** → **Draft a new release**
2. **Choose a tag** → type the new version number (e.g. `1XX.X.X`) → **Create new tag on publish**
3. Title: follow your release name style (e.g. `⛐ It's the "..." release:`)
4. Attach both files:
   - `ducksteps.1XX.X.X.Setup.exe`
   - `ducksteps.1XX.X.X.Standalone.7z`
5. Release notes: include SHA256 hashes and VirusTotal links for both files
6. Publish — GitHub creates the tag on the default branch at publish time
7. Changelog: Update Changelog.md in the Repos /Docs/ folder.

---

## 💻 Step 15 — Build and Package Skylake Variant

```bash
export MOZCONFIG=/d/mozilla-source/ducksteps/.mozconfig-Legacy
export OBJDIR="D:/ducksteps-obj/esr1XX-Legacy"
./mach clobber
./mach build
./mach run
./mach package
```

- Re-run steps 11-14 using the following naming convention: ducksteps.1XX.X.X.Legacy.Setup.exe and ducksteps.1XX.X.X.Legacy.Standalone.7z
- Raw outputs after this step:

| File | Path |
|---|---|
| Installer EXE | `D:/ducksteps-obj/esr1XX-Legacy/dist/install/sea/firefox-1XX.X.X.en-US.win64.installer.exe` |
| Standalone ZIP | `D:/ducksteps-obj/esr1XX-Legacy/dist/firefox-1XX.X.X.en-US.win64.zip` |

- To revert to zen5 building ( change 1XX info):
```
export MOZCONFIG=/d/mozilla-source/ducksteps/.mozconfig
export OBJDIR="D:/ducksteps-obj/esr1XX"
```
---

## ☑️ Release checklist

- [ ] `version.txt` and `version_display.txt` show the correct new version
- [ ] Build completed without fatal errors
- [ ] `./mach run` launches and shows correct ducksteps branding (no Nightly purple)
- [ ] `package.sh` completed and installer is ~72 MB (not under 1 MB)
- [ ] `upx -t` returned `[OK]` on the Setup.exe
- [ ] Both files checksummed and submitted to VirusTotal
- [ ] exe_7z_archive.py UPX patch applied (check after every rebase)
- [ ] Release notes include SHA256 hashes and VirusTotal links for both files

---

## 📝 Notes

- **Do not use `git pull` at any point** in this workflow — your branch diverges from upstream intentionally.
- **Detached HEAD warnings** from git are harmless. The rebase workflow keeps you on `esr1XX`.
- **NSIS warnings 6010, 6012, 9000** during packaging are pre-existing upstream. Harmless, appear in every Firefox build.
- **`rcedit-x64.exe`** is correct for win64 builds. The x86 binary in the same folder is unused.
- **`instrumented/`** in the objdir is the PGO training build. Never distribute from it.
- **UPX 3.95w** (2018) is what Mozilla's toolchain ships internally. Your standalone UPX 5.1.0 install is not invoked during the build.
