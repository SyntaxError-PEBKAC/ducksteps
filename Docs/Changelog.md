# Changelog

All releases of ducksteps. Newest first.

---

## [140.9.1] — 2026-04-09
⛐ It's the "security patch, no drama" release:

🔄  Updated to Firefox ESR 140.9.1. No build system changes, no new flags — just Mozilla patching things that needed patching.

🛡️  Addressed three high-severity CVEs from Mozilla Foundation Security Advisory 2026-27 (April 7, 2026): CVE-2026-5732 (integer overflow in text rendering), CVE-2026-5731 (memory safety bugs shared across ESR 115.34.0/140.9.0/Firefox 149.0.1), and CVE-2026-5734 (memory safety bugs in ESR 140.9.0/Firefox 149.0.1). Two of the three showed evidence of memory corruption with plausible RCE potential.

🚨  VirusTotal: two flags (Arctic Wolf, Jiangmin) on Setup.exe — same compression heuristic suspects as always. Standalone clean.

SHA256:
- `ducksteps.140.9.1.Setup.exe` — `32903e15b7d1e73574ad2651c930dbfc416dd666679a45dd5b77f857ea24e339`

- `ducksteps.140.9.1.Standalone.7z` — `2375250417db5f06e95efe52b93fbd5e731e95999954f3791ee8ce37aa5e587c`

---

## [140.9.0] — 2026-03-25
⛐ It's the "homework turned in on time" release:

🔄  Updated to Firefox ESR 140.9.0 release build (stable over latest-available).

🎂  Synchronized release date with Mozilla's ESR cadence — now shipping same-day as upstream ESR.

🛡️  AV false positive heads-up: compression flags (higher compression + file breakup) trigger suspicious-file detections on some scanners. Passed local Windows AV. VirusTotal: one flag (Jiangmin).

👩🏼‍🏫  Noted: custom PGO training scripts are coming. The duck will waddle faster. (coming soon™️)

SHA256:
- `ducksteps.140.9.0.Setup.exe` — `00347cd7d8685161b7f339ca1a46076c8b7916b43f89c1d17dc267fd06a585df`

- `ducksteps.140.9.0.Standalone.7z` — `a767b061579337e2c4e056fca3c99ef67f35cae4aedf2368f0206edf982f09d4`

---

## [140.8.0_PGO] — 2026-02-14
⛐ It's the "my bad, PGO was off!" release:

🔄  Updated to latest upstream ESR 140.x files.

🧠  Rebuilt with PGO correctly enabled — previous build had the flag silently missing.

🧹  Removed ccache — conflicts with PGO builds; user performance wins over compile time.

🗜️  Compressed Setup.exe further with additional UPX flags (`--best`, `--lzma`, `--ultra-brute`).

🛡️  AV heads-up: aggressive compression triggers scanner heuristics. Passed local Bitdefender. VirusTotal: two flags (Arctic Wolf, Jiangmin).

SHA256:
- `ducksteps-140.8.0-Setup-PGO.exe` — `5cc189c72f656dcd1fd470d27c035fa3e2c00233f73697823dee619cb9c8031f`

- `ducksteps-140.8.0-Standalone-PGO.7z` — `bc1566add7ac218bee59556923f72612f6c7114616dc90c4ea850d391a78ff02`

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

SHA256:
- `ducksteps-140.8.0-Setup` — `2cc410d988b9db279e701126555ae4b3c10a5cb0c881d4523bc2e82f2f0fe253`

- `ducksteps-140.8.0-Standalone` — `1867f5a197685d2896d8069ff92f62c64251f048a326fb5fe0d10c74778e0d53`

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

SHA256:
- `Ryfox 1.0.0 Setup.exe` — `6915169da6b66a17efe167d309ce7f033aeda750d9310fc1b9d33644e6c55408`

- `Ryfox 1.0.0 Setup.7z` — `f2a56d2537e0b7a9db5e483f9eb3acb92ef3a85122235efd6a507e04655afb13`
