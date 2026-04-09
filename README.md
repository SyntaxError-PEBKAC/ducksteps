🦆 ducksteps

A custom Windows build of Firefox ESR, compiled from source with Zen 5 CPU tuning, full LTO, and PGO enabled.

If you're running a Ryzen 9000, Ryzen AI 300, Threadripper PRO 9000, or EPYC 9005 and you want a browser that actually uses your hardware — this is it.

---
🤔 Why ducksteps exists

Google killing Manifest V2 support, combined with OAuth2 breakage in Chromium, forced me off my previous browser (Chromium_Clang). Firefox had the best extension compatibility, but the official Windows build leaves a lot of CPU performance on the table. So I built my own.
ducksteps is compiled with:

🎯 -march=znver5 -mtune=znver5 — Zen 5 instruction set and tuning, not a generic x86-64 baseline

🔗 Full LTO — link-time optimization across the entire binary

🧠 PGO — profile-guided optimization trained on real browsing workloads

🦾 clang-cl / lld-link — LLVM toolchain throughout, no MSVC codegen

The result is a browser that benchmarks noticeably higher than the official release on the same hardware.

---
📋 Requirements

OS: Windows 11 (64-bit)
CPU: AMD Zen 5 architecture — the build will run on other x86-64 CPUs but will likely crash or behave incorrectly due to the -march=znver5 flag generating instructions older CPUs don't support

✅ Ryzen 9000 series (9600X, 9700X, 9900X, 9950X, 9950X3D, etc.)

✅ Ryzen AI 300 series

✅ Threadripper PRO 9000 series

✅ EPYC 9005 series


GPU: Any — tested on RTX 4080 Super

---
📥 Download

Grab the installer or standalone ZIP from the Releases page.

ducksteps.X.X.X.Setup.exe — Installer — installs like a normal app

Standalone.7z — Portable — extract and run, no installation

SHA256 hashes and VirusTotal results are included with every release.

AV flags from Jiangmin are a known false positive caused by aggressive 7zip compression settings — not malware.

---
🏁 Benchmarks

Tested on AMD 9950X3D / RTX 4080 Super / 48GB DDR5 / Windows 11 @ 1080p 60Hz.

BenchmarkScores:

Speedometer 3.135.5

JetStream 2.2336.123

MotionMark 1.3.12136.29

Speedometer 2.1624

---
🔧 Build configuration

.mozconfig and the full build runbook are in /docs.

Key flags: --enable-lto=full, MOZ_PGO=1, -march=znver5 -mtune=znver5, clang-cl, lld-link.

---
⚖️ Legal

ducksteps is an unofficial build. "Firefox" and the Firefox logo are trademarks of Mozilla. ducksteps is not affiliated with or endorsed by Mozilla. 

Source: mozilla-firefox/firefox. Licensed under MPL 2.0.

---
🤷 Honest notes

This is the first thing I've ever compiled into something I could share, and I am extremely inexperienced. Starting with a web browser was probably not the smartest "Hello World" project, but I wanted a browser that fully utilized my 9950X3D and this is what I ended up with.

I relied heavily on ChatGPT and Claude to get across both the start and finish lines. Human feedback is always welcome — open an issue or hit the Discussions tab.
