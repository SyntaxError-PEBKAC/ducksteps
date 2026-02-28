# ducksteps Release Runbook (Windows 11, beginner-friendly)

This is the **manual** release process used for ducksteps.

It is written for my current setup:
- Source repo: `D:\mozilla-source\ducksteps`
- Object directory: `D:\ducksteps-obj\esr140`
- Shells used: **MozillaBuild (MSYS bash)** + **PowerShell**
- Upload method: **GitHub Releases web UI**

---

## 1) Update to a new Firefox ESR version

I usually do this for:
- **Monthly ESR security update**
- **Emergency ESR security release** (out-of-band)

### 1.1 Pick the target ESR version
Use Mozilla product details (or ESR release notes) and note the target version (example: `140.8.0`).
https://product-details.mozilla.org/1.0/firefox_versions.json

### 1.2 Sync your source tree
In **MozillaBuild shell**:

```bash
cd /d/mozilla-source/ducksteps

# Make sure working tree is clean before updating.
git status

# Pull latest changes from the tracked ESR branch.
git pull --ff-only
```

If I track a specific branch/tag, switch to it first, then pull.

### 1.3 Verify `.mozconfig` still has your intended options
Your current important options are:
- `--enable-release`
- `--enable-optimize`
- `--enable-lto=full`
- `MOZ_PGO=1` (**as `ac_add_options`, not `mk_add_options`**)
- `--with-branding=browser/branding/ducksteps`
- `clang-cl` + `lld-link`
- `export CFLAGS="-march=znver5 -mtune=znver5"`
- `export CXXFLAGS="-march=znver5 -mtune=znver5"`
- `MOZ_OBJDIR=D:/ducksteps-obj/esr140`

If `MOZ_OBJDIR` still includes old ESR in the path name, either:
- keep it as-is (works technically), or
- rename it for clarity before the build (example: `esr141`).

### 1.4 My known working .mozconfig file for reference purposes as of 28-February-2026:
```
ac_add_options --enable-application=browser
ac_add_options --enable-release
ac_add_options --disable-debug
ac_add_options --enable-unified-build

# Optimized build
ac_add_options --enable-optimize

# Full LTO
ac_add_options --enable-lto=full

# Full local build (not artifact)
ac_add_options --disable-artifact-builds

# PGO
ac_add_options MOZ_PGO=1

# Parallelism (-1 for all available, or total CPU threads you want to dedicate to the build on your hardware. 32 is max possible for 9950X3D)
mk_add_options MOZ_MAKE_FLAGS=-j32

# Toolchain
export CC=clang-cl
export CXX=clang-cl
export LINKER=lld-link
export HOST_LINKER=lld-link

# Zen 5 tuning
export CFLAGS="-march=znver5 -mtune=znver5"
export CXXFLAGS="-march=znver5 -mtune=znver5"

# Objdir
mk_add_options MOZ_OBJDIR=D:/ducksteps-obj/esr140

# Custom branding directory (relative to topsrcdir)
ac_add_options --with-branding=browser/branding/ducksteps

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

This opens ducksteps to quickly verify it starts.

---

## 3) Package release artifacts

In **MozillaBuild shell**:

```bash
cd /d/mozilla-source/ducksteps
./mach package
```

Expected raw outputs:
- Installer EXE:  
  `D:\ducksteps-obj\esr140\dist\install\sea\firefox-<ver>.en-US.win64.installer.exe`
- Standalone archive (zip from mach package):  
  `D:\ducksteps-obj\esr140\dist\firefox-<ver>.en-US.win64.zip`

---

## 4) Convert standalone package to release `.7z`

Use the existing 7-Zip workflow in **PowerShell** (or 7-Zip GUI).
- 7z Archive format, 9 - Ultra compression level, * LZMA2 compression method, 3840 MB dictionary size, 273 word size, solid block size, 3 CPU threads.

Goal output file name:
- `ducksteps-<ver>-Standalone.7z`

Example target name:
- `ducksteps-140.8.0-Standalone.7z`

Keep the file in a release staging folder (for example Desktop or a `releases` folder).

---

## 5) Apply UPX to installer (official step)

UPX is part of my official release process and should use maximum compression.

In **PowerShell** (adapt to your exact preferred command):

```powershell
$src = "D:\ducksteps-obj\esr140\dist\install\sea\firefox-<ver>.en-US.win64.installer.exe"
$dst = "D:\ducksteps-obj\esr140\dist\install\sea\ducksteps-<ver>-Setup.exe"
Copy-Item $src $dst -Force
upx --best --lzma --ultra-brute $dst
upx -t $dst
```

If the installed UPX build does not support `--ultra-brute`, keep the best supported maximum mode (`--best --lzma`) and still run `upx -t`.

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

## 7) Checksum verification

Use 7zip to extract SHA256 checksum of each of the above files and submit both to VirusTotal for scanning.


## 8) Version tagging and GitHub release publish

## 8.1 Create a git tag for the release
In **MozillaBuild shell** at repo root:

```bash
cd /d/mozilla-source/ducksteps
git status

# Example tag format 
  #ducksteps-140.8.0

git tag -a ducksteps-<ver> -m "ducksteps <ver>"
git push origin ducksteps-<ver>
```

## 8.2 Publish in GitHub web UI
1. Open repo → **Releases** → **Draft a new release**.
2. Select tag: `ducksteps-<ver>`.
3. Title example: `ducksteps <ver>`.
4. Attach:
   - `ducksteps-<ver>-Setup.exe`
   - `ducksteps-<ver>-Standalone.7z`
5. Add short notes (ESR base version + key changes/fixes, SHA256 checksums and VirusTotal links).
6. Publish release.

---

## 9) What good looks like (release checklist)

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

## 10) Fast recovery when something breaks

In **MozillaBuild shell**:

```bash
cd /d/mozilla-source/ducksteps
./mach clobber
./mach configure
./mach build
./mach package
```

If the objdir is deeply inconsistent, delete the full objdir and rebuild from configure.
