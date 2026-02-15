# ducksteps Release Runbook (Windows 11, beginner-friendly)

This is the **manual** release process used for ducksteps.

It is written for your current setup:
- Source repo: `D:\mozilla-source\ducksteps`
- Object directory: `D:\ducksteps-obj\esr140`
- Shells used: **MozillaBuild (MSYS bash)** + **PowerShell**
- Upload method: **GitHub Releases web UI**

---

## 1) Update to a new Firefox ESR version

You usually do this for:
- **Monthly ESR security update**
- **Emergency ESR security release** (out-of-band)

### 1.1 Pick the target ESR version
Use Mozilla product details (or ESR release notes) and note the target version (example: `140.8.0`).

### 1.2 Sync your source tree
In **MozillaBuild shell**:

```bash
cd /d/mozilla-source/ducksteps

# Make sure working tree is clean before updating.
git status

# Pull latest changes from your tracked ESR branch.
git pull --ff-only
```

If you track a specific branch/tag, switch to it first, then pull.

### 1.3 Verify `.mozconfig` still has your intended options
Your current important options are:
- `--enable-release`
- `--enable-optimize`
- `--enable-lto=full`
- `MOZ_PGO=1` (**as `ac_add_options`, not `mk_add_options`**)
- `--with-branding=browser/branding/ducksteps`
- `clang-cl` + `lld-link`
- Zen 5 C/C++ flags
- `MOZ_OBJDIR=D:/ducksteps-obj/esr140`

If `MOZ_OBJDIR` still includes old ESR in the path name, either:
- keep it as-is (works technically), or
- rename it for clarity before the build (example: `esr141`).

---

## 2) Build ducksteps on Windows 11

## 2.1 Configure/build (MozillaBuild shell)

```bash
cd /d/mozilla-source/ducksteps
./mach clobber
./mach configure
./mach build
```

> `./mach clobber` is the safe default for release builds. It avoids stale outputs.

## 2.2 Optional smoke run

```bash
./mach run
```

This opens ducksteps so you can quickly verify it starts.

---

## 3) Package release artifacts

In **MozillaBuild shell**:

```bash
cd /d/mozilla-source/ducksteps
./mach package
./mach installer
```

Expected raw outputs:
- Installer EXE:  
  `D:\ducksteps-obj\esr140\dist\install\sea\firefox-<ver>.en-US.win64.installer.exe`
- Standalone archive (zip from mach package):  
  `D:\ducksteps-obj\esr140\dist\firefox-<ver>.en-US.win64.zip`

---

## 4) Convert standalone package to release `.7z`

Use your existing 7-Zip workflow in **PowerShell** (or 7-Zip GUI).

Goal output file name:
- `ducksteps-<ver>-Standalone.7z`

Example target name:
- `ducksteps-140.8.0-Standalone.7z`

Keep the file in a release staging folder (for example Desktop or a `releases` folder).

---

## 5) Apply UPX to installer (official step)

UPX is part of your official release process and should use maximum compression.

In **PowerShell** (adapt to your exact preferred command):

```powershell
$src = "D:\ducksteps-obj\esr140\dist\install\sea\firefox-<ver>.en-US.win64.installer.exe"
$dst = "D:\ducksteps-obj\esr140\dist\install\sea\ducksteps-<ver>-Setup.exe"
Copy-Item $src $dst -Force
upx --best --lzma --ultra-brute $dst
upx -t $dst
```

If your installed UPX build does not support `--ultra-brute`, keep your best supported maximum mode (`--best --lzma`) and still run `upx -t`.

Goal output file name:
- `ducksteps-<ver>-Setup.exe`

Example:
- `ducksteps-140.8.0-Setup.exe`

---

## 6) Final expected release files

Before upload, you should have exactly these two release artifacts:

1. `ducksteps-<ver>-Setup.exe`
2. `ducksteps-<ver>-Standalone.7z`

Example:
1. `ducksteps-140.8.0-Setup.exe`
2. `ducksteps-140.8.0-Standalone.7z`

---

## 7) Version tagging and GitHub release publish

## 7.1 Create a git tag for the release
In **MozillaBuild shell** at repo root:

```bash
cd /d/mozilla-source/ducksteps
git status

# Example tag format (choose one and stay consistent):
# ducksteps-140.8.0
# v140.8.0-ducksteps

git tag -a ducksteps-<ver> -m "ducksteps <ver>"
git push origin ducksteps-<ver>
```

## 7.2 Publish in GitHub web UI
1. Open repo → **Releases** → **Draft a new release**.
2. Select tag: `ducksteps-<ver>`.
3. Title example: `ducksteps <ver>`.
4. Attach:
   - `ducksteps-<ver>-Setup.exe`
   - `ducksteps-<ver>-Standalone.7z`
5. Add short notes (ESR base version + key changes/fixes).
6. Publish release.

---

## 8) What good looks like (release checklist)

A release is "good" when all checks below pass:

- Build/config includes expected knobs:
  - Branding: `browser/branding/ducksteps`
  - LTO enabled
  - PGO enabled (`MOZ_PGO=1` visible in build config/about:buildconfig)
- `./mach build` completes without fatal errors.
- `./mach run` launches successfully.
- Packaging produces both installer + standalone package.
- UPX compression command succeeds and `upx -t` passes on final installer.
- Final release filenames follow your naming scheme exactly.
- Git tag exists remotely.
- GitHub Release contains both files and correct version text.

---

## 9) Fast recovery when something breaks

In **MozillaBuild shell**:

```bash
cd /d/mozilla-source/ducksteps
./mach clobber
./mach configure
./mach build
./mach package
./mach installer
```

If installer outputs look stale, clear installer staging then rebuild:

```bash
rm -rf /d/ducksteps-obj/esr140/browser/installer
rm -rf /d/ducksteps-obj/esr140/dist/install
./mach build browser/installer
./mach installer
```

If the objdir is deeply inconsistent, delete the full objdir and rebuild from configure.
