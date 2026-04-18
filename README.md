🦆 ducksteps

A custom Windows build of Firefox ESR, compiled from source with Zen 5 or AVX2 CPU tuning, full LTO, and PGO enabled.

If you're running a Ryzen 9000, Ryzen AI 300, Threadripper PRO 9000, or EPYC 9005 and you want a browser that actually uses your hardware — this is it.

If you're on an older CPU that has AVX2, BMI1, BMI2, FMA, LZCNT, MOVBE, and POPCNT support download the LEGACY version. That covers most Intel chips from Broadwell (2014) onward and most AMD chips from Excavator (2015) onward! Welcome to the party AVX2 users!

---
🤔 Why ducksteps exists

Google killing Manifest V2 support, combined with OAuth2 breakage in Chromium, forced me off my previous browser (Chromium_Clang). Firefox had the best extension compatibility, but the official Windows build leaves a lot of CPU performance on the table. So I built my own.
ducksteps is compiled with:

🎯 `-march=znver5 -mtune=znver5 — Zen 5 instruction set and tuning, not a generic x86-64 baseline`
OR
`-march=skylake -mtune=skylake — AVX2 instruction set and tuning, (also) not a generic x86-64 baseline`

🔗 Full LTO — link-time optimization across the entire binary

🧠 PGO — profile-guided optimization trained on 80+ real browsing workloads

🦾 clang-cl / lld-link — LLVM toolchain throughout, no MSVC codegen

The result is a browser that benchmarks noticeably higher than the official release on the same hardware.

---
📋 Requirements

OS: Windows 11 (64-bit)
CPU: AMD Zen 5 architecture:

✅ Ryzen 9000 series (9600X, 9700X, 9900X, 9950X, 9950X3D, etc.)

✅ Ryzen AI 300 series

✅ Threadripper PRO 9000 series

✅ EPYC 9005 series

🖳 AVX2 `Legacy` Version now available for most CPUs made in 2014 or later.

GPU: Any — tested on RTX 4080 Super

---
📥 Download

Grab the correct installer or standalone ZIP from the Releases page.

`ducksteps.X.X.X.Setup.exe` —ZEN5 Installer — installs like a normal app

`ducksteps.X.X.X.Standalone.7z` — ZEN5 Portable — extract and run, no installation

`ducksteps.X.X.X.Legacy.Setup.exe` — Installer for older PCs — installs like a normal app

`ducksteps.X.X.X.Legacy.Standalone.7z` — Portable for older PCs — extract and run, no installation


SHA256 hashes and VirusTotal results are included with every release.

AV flags from Jiangmin are a known false positive caused by aggressive 7zip compression settings — not malware.

---
⚖️ Legal

ducksteps is an unofficial build. "Firefox" and the Firefox logo are trademarks of Mozilla. ducksteps is not affiliated with or endorsed by Mozilla. 

Source: mozilla-firefox/firefox. Licensed under MPL 2.0.

---
🤷 Honest notes

This is the first thing I've ever compiled into something I could share, and I am extremely inexperienced. Starting with a web browser was probably not the smartest "Hello World" project, but I wanted a browser that fully utilized my 9950X3D and this is what I ended up with. I hope you enjoy it!

I relied heavily on ChatGPT and Claude to get across both the start and finish lines. Human feedback is always welcome — open an issue or hit the Discussions tab.
