# Changelog

All releases of ducksteps. Newest first.

---

## [140.10.1] — 2026-04-29
⛐ It's the "memory corruption and really long build days" release:

🔄 Updated to Firefox ESR 140.10.1.

🛡️ Addressed CVE-2026-7321 (WebRTC sandbox escape, CVSS 9.6 — the one that actually prompted the point release), CVE-2026-7322 (memory safety bugs with plausible RCE potential across ESR 115/140 and Firefox 150), and CVE-2026-7323 (additional memory safety bugs in ESR 140.10.0 and Firefox 150). Mozilla Foundation Security Advisory 2026-36. The WebRTC one had "critical" written all over it — good patch cycle to stay current on.

🧠 This is the 5th build using the custom PGO training infrastructure. The extension now drives 87 sites through realistic scroll patterns, video playback, SPA hydration, map interactions, and speed tests before handing off to a clean shutdown. Each training run clocks in around 121 minutes. Each full build is around 190 minutes. The duck is very well trained at this point.

🗜️ Retired UPX compression on the installer stub entirely. UPX 5.x triggered Malwarebytes AI false positives at every compression level tested — including -1. Not worth the 66KB. Zero VirusTotal flags on both files this release.

🔧 Committed the custom PGO and UPX patches to the branch so they survive rebases automatically. Future releases won't require the manual patch dance that this one did.

---

## [140.10.0] — 2026-04-21
⛐ It's the "the duck went to the gym" release:

🔄 Updated to Firefox ESR 140.10.0. Picked up today's upstream security patch.

🛡️ Patched 13 high-severity CVEs from MFSA 2026-32 (April 21, 2026). Highlights: use-after-free in the DOM (CVE-2026-6746), use-after-free in WebRTC (CVE-2026-6747), uninitialized memory in Web Codecs (CVE-2026-6748/6751), privilege escalation in WebRender (CVE-2026-6750), use-after-free in the JS engine (CVE-2026-6754), and a broad set of memory safety bugs with plausible RCE potential (CVE-2026-6785/6786). Full advisory: https://www.mozilla.org/en-US/security/advisories/mfsa2026-32/

🧠 Rebuilt the PGO training infrastructure from scratch as a proper WebExtension. The extension drives all 87 sites autonomously through scroll behaviors, video playback, SPA hydration, map panning, and speed tests, then navigates to a localhost-served shutdown page that calls Quitter.quit() for a clean profraw flush. This is the 5th refinement build using custom training, with improved tunings after each run.

🦾 Added RUSTFLAGS="-C target-cpu=znver5 -C opt-level=3" (Zen 5) and "-C target-cpu=haswell -C opt-level=3" (Legacy). The Rust side of the build was previously compiling to a generic target — it's now CPU-tuned to match the C/C++ flags.

🖳 Switched the Legacy build to -march=x86-64-v3 -mtune=generic. Covers Intel Haswell (2013) and later, and most AMD chips from Excavator (2015) onward. The generic tune keeps it fast across both vendors.

🔧 Patched profileserver.py with a 3-hour watchdog thread (safety net if a training site hangs), a @response_file workaround for Windows' 32K command-line limit when llvm-profdata merge chokes on hundreds of profraw filenames, and a Speedometer 3 HTTP server on port 8000 alongside the existing port 8888 server.

🚫 Disabled the updater, maintenance service, default-browser-agent, and crashreporter at compile time. None of them are used, and they were just sitting there consuming memory and storage for no reason.

🧪 Tested --enable-optimize="-O3" and --enable-optimize="-O3 /Gy". Both caused lld-link duplicate symbol errors in mozglue during the PGO instrumented phase — -O3 as a bare flag replaces Mozilla's default flag expansion in a way that breaks jemalloc operator handling. Reverted to bare --enable-optimize. Documented here so I remember not to try this again.

🗜️ Upgraded UPX from 3.95w (2018) to 5.1.1 (2026). No meaningful size change, but years of fixes baked in. Turns out 5.x's defaults (--best --lzma --ultra-brute) are spicy enough to turn two VirusTotal flags into six, so I patched exe_7z_archive.py to dial it back to -6 with no algorithm flags. That added 1-2MB more total filesize, but there are no more false positives from VirusTotal.

⏱️ Fun facts: each PGO run alone takes ~112 minutes, and a complete build now clocks in at ~190 minutes. (pls send RAM & caffeine)

🤖 Fun fact # 2 (3?): I spent a painful number of Claude Opus 4.6 credits on this release, and Anthropic waited until I was basically done to drop Opus 4.7 — which uses over a third fewer tokens per task. I'm not saying the timing was personal. I'm just saying the timing was personal.

---

## [140.9.1] — 2026-04-09
⛐ It's the "security patch, everyone's welcome!" release:

🔄  Updated to Firefox ESR 140.9.1. Just Mozilla patching things that needed patching.

🍾 First Skylake and newer release! Download the Legacy version if you don't have a AMD Zen 5 CPU. This build is compiled with:
-march=skylake -mtune=skylake
It requires a CPU with AVX2, BMI1, BMI2, FMA, LZCNT, MOVBE, and POPCNT support.
In practice that covers most Intel chips from Broadwell (2014) onward and most AMD chips from Excavator (2015) onward.

🛡️  Addressed three high-severity CVEs from Mozilla Foundation Security Advisory 2026-27 (April 7, 2026): CVE-2026-5732 (integer overflow in text rendering), CVE-2026-5731 (memory safety bugs shared across ESR 115.34.0/140.9.0/Firefox 149.0.1), and CVE-2026-5734 (memory safety bugs in ESR 140.9.0/Firefox 149.0.1). Two of the three showed evidence of memory corruption with plausible RCE potential.

🚨  VirusTotal: two flags (Arctic Wolf, Jiangmin) on Setup.exe — same compression heuristic suspects as always. Standalone clean.

---

## [140.9.0] — 2026-03-25
⛐ It's the "homework turned in on time" release:

🔄  Updated to Firefox ESR 140.9.0 release build (stable over latest-available).

🎂  Synchronized release date with Mozilla's ESR cadence — now shipping same-day as upstream ESR.

🛡️  AV false positive heads-up: compression flags (higher compression + file breakup) trigger suspicious-file detections on some scanners. Passed local Windows AV. VirusTotal: one flag (Jiangmin).

👩🏼‍🏫  Noted: custom PGO training scripts are coming. The duck will waddle faster. (coming soon™️)

---

## [140.8.0_PGO] — 2026-02-14
⛐ It's the "my bad, PGO was off!" release:

🔄  Updated to latest upstream ESR 140.x files.

🧠  Rebuilt with PGO correctly enabled — previous build had the flag silently missing.

🧹  Removed ccache — conflicts with PGO builds; user performance wins over compile time.

🗜️  Compressed Setup.exe further with additional UPX flags (`--best`, `--lzma`, `--ultra-brute`).

🛡️  AV heads-up: aggressive compression triggers scanner heuristics. Passed local Bitdefender. VirusTotal: two flags (Arctic Wolf, Jiangmin).

---

## [140.8.0] — 2026-01-31
⛐ It's the "I DID A THING!" release:

🌐  Renamed Nightly to Ryfox.

😐  Renamed Ryfox to ducksteps in accordance with Mozilla naming recommendations.

🏞️  Created an icon set via ChatGPT and implemented it in installer and browser. Not an artist — just wanted something welcoming and scalable. Proper iconography is a future problem.

💾  Moved working directories to ReFS storage for faster builds from source.

🚄  Configured ccache for faster compiling.

🐞  Patched numerous minor compilation bugs.

🪨  Swapped codebase from Nightly to ESR (major updates every 6–12 months, monthly security/bugfix cadence). More stable, easier to keep on a normal release schedule.

🗜️  Compressed standalone 7z as much as possible. (Level 9 Ultra, LZMA2, 3840 MB dict, 273 word size, solid block, 3 threads)

🤷🏽‍♂️  Unable to compress Setup.exe further — the two files ended up within 2.65 MB of each other.

💯  Version numbering now matches compiled Firefox version going forward.

---

## [v1.0.0] — 2025-12-09
Initial alpha release. Shipped as "Ryfox 1.0.0."

🦊  Built on Firefox Nightly 142.0a1 (2025-12-08).

🧰  Toolchain: VS 2022 Build Tools 17.14.36717.8, Rustup 1.28.2, Python 3.14.2, Chocolatey 2.6.0, ccache 4.12.2.

Benchmarks (9950X3D / RTX 4080 Super / 48GB DDR5 / 1080p 60Hz):

- Speedometer 3.1: 35.5

- JetStream 2.2: 336.123

- MotionMark 1.3.1: 2136.29

- Speedometer 2.1: 624
