🦆 ducksteps

A custom Windows build of Firefox ESR, compiled from source with Zen 5 or AVX2 CPU tuning, full LTO, and tuned PGO enabled.

---
🤔 Why ducksteps exists

Google killing Manifest V2 support, combined with OAuth2 breakage in Chromium, forced me off my previous browser (Chromium_Clang). Firefox had the best extension compatibility, but the official Windows build leaves a lot of CPU performance on the table. So I built my own.
ducksteps is compiled with:

🎯 `-march=znver5 -mtune=znver5` — Zen 5 instruction set and tuning, not a generic x86-64 baseline

OR

`-march=x86-64-v3 -mtune=generic` — AVX2 instruction set and tuning, (also) not a generic x86-64 baseline

🔗 Full LTO — link-time optimization across the entire binary

🧠 PGO — profile-guided optimization trained on 80+ real browsing workloads

🦾 clang-cl / lld-link — LLVM toolchain throughout, no MSVC codegen

---
📊 Benchmarks (Zen 5 build vs. stock Firefox ESR 140.11.0)

Tested on AMD Ryzen 9950X3D / 48GB DDR5 / RTX 4080 Super / Windows 11 25H2.

ducksteps renders animations and scrolling **~10% faster** than stock Firefox on the same hardware, and handles real-world JavaScript **~2% faster**. It scores ~2% lower on short synthetic microbenchmarks — that's a known, deliberate tradeoff from tuning PGO for real browsing instead of benchmark loops.

Full numbers, methodology, and per-test breakdowns: [PerformanceBenchmark.md](Docs/PerformanceBenchmark.md).

---
📋 Requirements

OS: Windows 11 (64-bit)
CPU: AMD Zen 5 architecture:

✅ Ryzen 9000 series (9600X, 9700X, 9900X, 9950X, 9950X3D, etc.)

✅ Ryzen AI 300 series

✅ Threadripper PRO 9000 series

✅ EPYC 9005 series

🖳 AVX2 `Legacy` Version now available for most CPUs made around 2013-15 or later.

GPU: Any — tested on RTX 4080 Super

If you're running a Ryzen 9000 series, Ryzen AI 300 series, Threadripper PRO 9000 series, or EPYC 9005 series — this build is compiled specifically for your silicon. Zen 5 only; no Intel equivalent exists.

If your CPU has AVX2, BMI1, BMI2, FMA, LZCNT, MOVBE, and POPCNT — download the Legacy version. In practice: most Intel chips from Haswell (2013) onward and most AMD chips from Excavator (2015) onward qualify. If you're unsure, check your CPU specs against that feature list before downloading.

---
📥 Download

Grab the correct installer or standalone ZIP from the Releases page.

`ducksteps.X.X.X.Setup.exe` —ZEN5 Installer — installs like a normal app

`ducksteps.X.X.X.Standalone.7z` — ZEN5 Portable — extract and run, no installation

`ducksteps.X.X.X.Legacy.Setup.exe` — Installer for older PCs — installs like a normal app

`ducksteps.X.X.X.Legacy.Standalone.7z` — Portable for older PCs — extract and run, no installation


SHA512 hashes and VirusTotal results are included with every release.

---
🔔 Update notifications

ducksteps does not update itself. Once a day it asks GitHub for the version number of the newest published release. If that version is newer than yours, a bar appears at the top of the window and the About dialog shows a Download link to that release's page. You then download and run the installer yourself.

The check is one anonymous request to `api.github.com`, with no cookies and no personal data sent. Nothing is downloaded or installed automatically. To turn it off, set `ducksteps.releasecheck.enabled` to `false` in `about:config`.

---
⚖️ Legal

ducksteps is an unofficial build. "Firefox" and the Firefox logo are trademarks of Mozilla. ducksteps is not affiliated with or endorsed by Mozilla. 

Source: mozilla-firefox/firefox. Licensed under MPL 2.0.

---
🤷 Honest notes

This is the first thing I've ever compiled into something I could share, and I am extremely inexperienced. Starting with a web browser was probably not the smartest "Hello World" project, but I wanted a browser that fully utilized my 9950X3D and this is what I ended up with. I hope you enjoy it!

I relied heavily on ChatGPT and Claude to get across both the start and finish lines. Human feedback is always welcome — open an issue or hit the Discussions tab.
