# Changelog

All releases of ducksteps. Newest first.

---

## [153.4.0] (30/September/2026)

⛐ It's the "Doing grown-up stuff" release!

🔄 Updated to Firefox ESR 153.4.0.

Pure upstream sync; no ducksteps-side changes this round.

🛡️ Addressed 62 CVEs from [Mozilla Foundation Security Advisory 2026-100](https://www.mozilla.org/en-US/security/advisories/mfsa2026-100/) (September 29, 2026). 

Sorry for the brief delay. I was busy doing super important grown-up stuff… DEFINITELY NOT playing Minecraft Dungeons 2 and ignoring my notifications alerts all day.

---

## [153.3.0] (16/September/2026)

⛐ It's the "mostly smooth sailing" release!

🔄 Updated to Firefox ESR 153.3.0.

Pure upstream sync; no ducksteps-side changes this round.

🛡️ Addressed 63 CVEs from [Mozilla Foundation Security Advisory 2026-93](https://www.mozilla.org/en-US/security/advisories/mfsa2026-93/) (September 15, 2026).

---

## [153.2.0] (2/September/2026)

⛐ It's the "out of this world" release!

🔄 Updated to Firefox ESR 153.2.0.

🔧 Started tracking build files that were never committed.

🏞️ Faded the logo's edges instead of cutting it off square.

🌌 Replaced the About dialog's flat purple with a space-themed backdrop.

📐 Enlarged and repositioned the About dialog wordmark.

🧠 Updated the PGO training corpus: dropped old.reddit.com, fixed the LibreSpeed self-abort.

🛡️ Addressed 24 CVEs from [Mozilla Foundation Security Advisory 2026-85](https://www.mozilla.org/en-US/security/advisories/mfsa2026-85/) (September 01, 2026). This round patches twenty-four CVEs (12 high, 5 moderate, 7 low severity).

---

## [153.1.0] (19/August/2026)

⛐ It's the "fifty-two CVEs, nineteen of them serious" release!

🔄 Updated to Firefox ESR 153.1.0.

🗑️ Removed the now-unused tools/upx-after-package.ps1 script.

🗓️ Fixed a stale date in the PGO training corpus metadata.

⚙️ Fixed incorrect wording on the "More from Mozilla" settings page.

🏷️ Data reporting notice now correctly refers to Mozilla as "they", not ducksteps as "we".

📡 Telemetry prompts now correctly name Mozilla as the data recipient, not the maintainer.

🛡️ Addressed 52 CVEs from [Mozilla Foundation Security Advisory 2026-77](https://www.mozilla.org/en-US/security/advisories/mfsa2026-77/) (August 18, 2026). This one's mostly patching holes; 19 high, 23 moderate, and 10 low severity CVEs squashed, nothing screaming louder than the rest but the high count alone is enough to not sit on this. Update when you get a sec.

---

## [153.0] (16/August/2026)

⛐ It's the "thirteen versions of catching up" release!

🔄 Updated to Firefox ESR 153.0. About dialog wordmark no longer overlaps the version text on the new line; Stub installer stylesheets resynced with ESR 153's markup; Installer wizard bitmap artifacts fixed; About dialog credits Mozilla and SyntaxError-PEBKAC, with What's New pointing at the changelog.

🆕 What ESR 153 brings over ESR 140 (thirteen Firefox versions at once):

- **Profiles and windows** - a proper profile manager (separate work / school / personal profiles with their own names, avatars and themes), Split View for two pages side by side, and Containers for staying signed into different accounts in one window.
- **Tabs and navigation** - reworked vertical tabs and tab groups, multi-tab copying and sharing, QR codes for sending a tab to your phone, and passwords reachable from the sidebar.
- **Address bar** - unit and time zone conversion, quick actions such as muting all audio, a colour picker, and copying a link straight to highlighted text on a page.
- **Media and graphics** - HDR video playback on Windows, better access to video actions from context menus, and experimental JPEG XL support behind Firefox Labs.
- **PDFs** - merge documents by dragging them into the sidebar, and add images as new pages from the built-in editor.
- **Privacy and security** - Fingerprinting Protection extended to Standard mode, stronger bounce-tracking protection, Safe Browsing V5, AES-256 for stored logins, a red location icon whenever a site is using your location, local network access now behind a permission prompt, and extensions no longer reading local files by default.
- **Translations and accessibility** - wider on-device translation, a dedicated translations page, and improved assistive technology support.
- **Settings** - redesigned, with some long-obsolete cookie options finally removed.

⚙️ Build and automation work this round:

- **Release automation** - the whole thing now runs from a script: it watches Mozilla for a new ESR tag, rebases the patch stack, builds both variants, smoke-tests them, packages, submits to VirusTotal, resolves the CVE list from Mozilla's advisory data and drafts these notes. Two approval gates (build, publish) are the only manual steps, both from a phone.
- **ESR 153 migration** - the ducksteps patch stack was rebased across 72,880 upstream commits. Two old upstream lint commits were dropped as obsolete, and the hand-written Rust lifetime workarounds went with them, since upstream now silences that lint itself.
- **Toolchain refresh** - ESR 153 needs newer tooling than 140 did: MSVC 14.50 (for the STL hardening ESR 153 enables by default), cbindgen 0.29, windows-rs 0.62, the Windows App SDK, DirectX Shader Compiler, and 7zz.
- **PGO** - both variants are still trained on the custom 88-site corpus rather than Mozilla's default workload, roughly 134 minutes of scripted real browsing per variant.
- **Optimisation** - unchanged and still the point of this build: Zen5 gets `-march=znver5 -mtune=znver5` with `target-cpu=znver5`, Legacy gets `-march=x86-64-v3` with `target-cpu=haswell`, and both get full LTO on top of PGO.
- **Packaging** - LZMA2 with a 384 MB dictionary and solid compression for the standalone archives. UPX stays off the installer stub, which keeps the antivirus false positives away.

🛡️ Addressed 60 CVEs from [Mozilla Foundation Security Advisory 2026-68](https://www.mozilla.org/en-US/security/advisories/mfsa2026-68/) (July 21, 2026). This one's a bigger deal than usual: it's the first build on the new ESR line, so it's dragging thirteen versions of upstream Firefox work along behind it instead of the usual trickle. You get an actual profile manager for keeping work and personal browsing apart, Split View for two pages side by side, Containers for juggling multiple accounts in one window, and vertical tabs plus tab groups that got a real rework this time. Windows users get HDR video playback, there's PDF merging and image insertion now, the address bar can convert units and timezones and pick colours, Fingerprinting Protection is on by default in Standard mode, saved logins get AES-256 encryption, and there's experimental JPEG XL support for the handful of people who care. Somewhere in all that, the usual pile of security fixes also rode along (20 high, 33 moderate, 7 low this round), but honestly they're the boring part this time.

High severity:

- **[CVE-2026-16349](https://www.cve.org/CVERecord?id=CVE-2026-16349)** Same-origin policy bypass in the DOM: Navigation component
- **[CVE-2026-16350](https://www.cve.org/CVERecord?id=CVE-2026-16350)** Incorrect boundary conditions in the Audio/Video: cubeb component
- **[CVE-2026-16362](https://www.cve.org/CVERecord?id=CVE-2026-16362)** Use-after-free in the WebRTC: Audio/Video component
- **[CVE-2026-16351](https://www.cve.org/CVERecord?id=CVE-2026-16351)** Sandbox escape due to use-after-free in the DOM: Navigation component
- **[CVE-2026-16352](https://www.cve.org/CVERecord?id=CVE-2026-16352)** Sandbox escape due to use-after-free in the Disability Access APIs component
- **[CVE-2026-16363](https://www.cve.org/CVERecord?id=CVE-2026-16363)** JIT miscompilation in the JavaScript: WebAssembly component
- **[CVE-2026-16364](https://www.cve.org/CVERecord?id=CVE-2026-16364)** Incorrect boundary conditions in the Audio/Video: Playback component
- **[CVE-2026-16365](https://www.cve.org/CVERecord?id=CVE-2026-16365)** Privilege escalation in the DOM: Workers component
- **[CVE-2026-16366](https://www.cve.org/CVERecord?id=CVE-2026-16366)** Privilege escalation in the DOM: Navigation component
- **[CVE-2026-16353](https://www.cve.org/CVERecord?id=CVE-2026-16353)** Invalid pointer in the DOM: Bindings (WebIDL) component
- **[CVE-2026-16354](https://www.cve.org/CVERecord?id=CVE-2026-16354)** Information disclosure in the Graphics: ImageLib component
- **[CVE-2026-16367](https://www.cve.org/CVERecord?id=CVE-2026-16367)** Sandbox escape due to invalid pointer in the Disability Access APIs component
- **[CVE-2026-16368](https://www.cve.org/CVERecord?id=CVE-2026-16368)** Incorrect boundary conditions in the JavaScript: WebAssembly component
- **[CVE-2026-16369](https://www.cve.org/CVERecord?id=CVE-2026-16369)** Integer overflow in the JavaScript: WebAssembly component
- **[CVE-2026-16355](https://www.cve.org/CVERecord?id=CVE-2026-16355)** JIT miscompilation in the JavaScript Engine: JIT component
- **[CVE-2026-16356](https://www.cve.org/CVERecord?id=CVE-2026-16356)** Sandbox escape due to use-after-free in the Disability Access APIs component
- **[CVE-2026-16357](https://www.cve.org/CVERecord?id=CVE-2026-16357)** Incorrect boundary conditions in the Graphics component
- **[CVE-2026-16411](https://www.cve.org/CVERecord?id=CVE-2026-16411)** Memory safety bugs fixed in Firefox 153
- **[CVE-2026-16412](https://www.cve.org/CVERecord?id=CVE-2026-16412)** Memory safety bugs fixed in Firefox ESR 140.13 and Firefox 153
- **[CVE-2026-16360](https://www.cve.org/CVERecord?id=CVE-2026-16360)** Memory safety bugs fixed in Firefox ESR 115.38, Firefox ESR 140.13 and Firefox 153

Moderate severity:

- **[CVE-2026-16370](https://www.cve.org/CVERecord?id=CVE-2026-16370)** Mitigation bypass in the DOM: Networking component
- **[CVE-2026-16371](https://www.cve.org/CVERecord?id=CVE-2026-16371)** Privilege escalation in the DOM: Navigation component
- **[CVE-2026-16372](https://www.cve.org/CVERecord?id=CVE-2026-16372)** Privilege escalation in the DOM: Content Processes component
- **[CVE-2026-16374](https://www.cve.org/CVERecord?id=CVE-2026-16374)** Information disclosure in the Framework component in DevTools
- **[CVE-2026-16375](https://www.cve.org/CVERecord?id=CVE-2026-16375)** Site isolation issue in the Networking: HTTP component
- **[CVE-2026-16376](https://www.cve.org/CVERecord?id=CVE-2026-16376)** Denial-of-service in the Graphics: WebGPU component
- **[CVE-2026-16377](https://www.cve.org/CVERecord?id=CVE-2026-16377)** Mitigation bypass in the PDF Viewer component
- **[CVE-2026-16378](https://www.cve.org/CVERecord?id=CVE-2026-16378)** Other issue in the DOM: Copy & Paste and Drag & Drop component
- **[CVE-2026-16379](https://www.cve.org/CVERecord?id=CVE-2026-16379)** Privilege escalation in the DOM: Content Processes component
- **[CVE-2026-16358](https://www.cve.org/CVERecord?id=CVE-2026-16358)** Site isolation issue in the Graphics: WebRender component
- **[CVE-2026-16380](https://www.cve.org/CVERecord?id=CVE-2026-16380)** Mitigation bypass in the Networking component
- **[CVE-2026-16381](https://www.cve.org/CVERecord?id=CVE-2026-16381)** Same-origin policy bypass in the Networking: DNS component
- **[CVE-2026-16382](https://www.cve.org/CVERecord?id=CVE-2026-16382)** Mitigation bypass in the DOM: Service Workers component
- **[CVE-2026-16383](https://www.cve.org/CVERecord?id=CVE-2026-16383)** Mitigation bypass in the DOM: Networking component
- **[CVE-2026-16384](https://www.cve.org/CVERecord?id=CVE-2026-16384)** Information disclosure due to uninitialized memory in the Graphics: WebGPU component
- **[CVE-2026-16385](https://www.cve.org/CVERecord?id=CVE-2026-16385)** Information disclosure due to uninitialized memory in the Graphics: WebGPU component
- **[CVE-2026-16386](https://www.cve.org/CVERecord?id=CVE-2026-16386)** Information disclosure due to uninitialized memory in the Graphics: WebGPU component
- **[CVE-2026-16387](https://www.cve.org/CVERecord?id=CVE-2026-16387)** Site isolation issue in the Networking component
- **[CVE-2026-16388](https://www.cve.org/CVERecord?id=CVE-2026-16388)** Sandbox escape in the DOM: Networking component
- **[CVE-2026-16389](https://www.cve.org/CVERecord?id=CVE-2026-16389)** Incorrect boundary conditions, integer overflow in the Libraries component in NSS
- **[CVE-2026-16390](https://www.cve.org/CVERecord?id=CVE-2026-16390)** Mitigation bypass in the Enterprise Policies component
- **[CVE-2026-16391](https://www.cve.org/CVERecord?id=CVE-2026-16391)** Information disclosure in the Storage: IndexedDB component
- **[CVE-2026-16392](https://www.cve.org/CVERecord?id=CVE-2026-16392)** JIT miscompilation in the JavaScript Engine: JIT component
- **[CVE-2026-16393](https://www.cve.org/CVERecord?id=CVE-2026-16393)** Incorrect boundary conditions in the Graphics: WebGPU component
- **[CVE-2026-16359](https://www.cve.org/CVERecord?id=CVE-2026-16359)** Incorrect boundary conditions in the Audio/Video: GMP component
- **[CVE-2026-16394](https://www.cve.org/CVERecord?id=CVE-2026-16394)** Mitigation bypass in the DOM: Security component
- **[CVE-2026-16395](https://www.cve.org/CVERecord?id=CVE-2026-16395)** Integer overflow in the Audio/Video component
- **[CVE-2026-16396](https://www.cve.org/CVERecord?id=CVE-2026-16396)** Privilege escalation in WebExtensions
- **[CVE-2026-16398](https://www.cve.org/CVERecord?id=CVE-2026-16398)** Site isolation issue in the Graphics component
- **[CVE-2026-16399](https://www.cve.org/CVERecord?id=CVE-2026-16399)** Site isolation issue in the DOM: Navigation component
- **[CVE-2026-16400](https://www.cve.org/CVERecord?id=CVE-2026-16400)** Information disclosure in the DOM: Security component
- **[CVE-2026-16401](https://www.cve.org/CVERecord?id=CVE-2026-16401)** Privilege escalation in the Data Loss Prevention component
- **[CVE-2026-16402](https://www.cve.org/CVERecord?id=CVE-2026-16402)** Integer overflow in the Graphics: ImageLib component

Low severity:

- **[CVE-2026-16403](https://www.cve.org/CVERecord?id=CVE-2026-16403)** Spoofing issue in the Address Bar component
- **[CVE-2026-16405](https://www.cve.org/CVERecord?id=CVE-2026-16405)** Information disclosure in the Networking: WebSockets component
- **[CVE-2026-16406](https://www.cve.org/CVERecord?id=CVE-2026-16406)** Mitigation bypass in the Networking component
- **[CVE-2026-16407](https://www.cve.org/CVERecord?id=CVE-2026-16407)** Mitigation bypass in the DOM: Service Workers component
- **[CVE-2026-16408](https://www.cve.org/CVERecord?id=CVE-2026-16408)** Integer overflow in the Audio/Video: Playback component
- **[CVE-2026-16409](https://www.cve.org/CVERecord?id=CVE-2026-16409)** Invalid pointer in the Security: PSM component
- **[CVE-2026-16410](https://www.cve.org/CVERecord?id=CVE-2026-16410)** JIT miscompilation in the JavaScript Engine: JIT component

---

## [140.13.0] (21/July/2026)

⛐ It's the "exploit code's already out there" release!

🔄 Updated to Firefox ESR 140.13.0. Pure upstream sync; no ducksteps-side changes this round.

🛡️ Addressed 32 CVEs from Mozilla Foundation Security Advisory 2026-70 (July 21, 2026). Two critical this cycle (a WebAssembly invalid pointer and a DOM Navigation site isolation bypass), both with public exploit code, though Mozilla reports no confirmed in-the-wild attacks yet. Also 16 high-severity patches (three sandbox escapes, two JIT miscompilations, four WebAssembly-related bugs), 13 moderate, 1 low. Heaviest cycle since 140.12.0's 29.

Critical severity:

- **[CVE-2026-15718](https://www.cve.org/CVERecord?id=CVE-2026-15718)** invalid pointer in the JavaScript: WebAssembly component (public exploit code exists)
- **[CVE-2026-15719](https://www.cve.org/CVERecord?id=CVE-2026-15719)** site isolation issue in the DOM: Navigation component (public exploit code exists)

High severity:

- **[CVE-2026-16349](https://www.cve.org/CVERecord?id=CVE-2026-16349)** same-origin policy bypass in the DOM: Navigation component
- **[CVE-2026-16350](https://www.cve.org/CVERecord?id=CVE-2026-16350)** incorrect boundary conditions in the Audio/Video: cubeb component
- **[CVE-2026-16351](https://www.cve.org/CVERecord?id=CVE-2026-16351)** sandbox escape via use-after-free in the DOM: Navigation component
- **[CVE-2026-16352](https://www.cve.org/CVERecord?id=CVE-2026-16352)** sandbox escape via use-after-free in the Disability Access APIs component
- **[CVE-2026-16353](https://www.cve.org/CVERecord?id=CVE-2026-16353)** invalid pointer in the DOM: Bindings (WebIDL) component
- **[CVE-2026-16354](https://www.cve.org/CVERecord?id=CVE-2026-16354)** information disclosure in the Graphics: ImageLib component
- **[CVE-2026-16355](https://www.cve.org/CVERecord?id=CVE-2026-16355)** JIT miscompilation in the JavaScript Engine: JIT component
- **[CVE-2026-16356](https://www.cve.org/CVERecord?id=CVE-2026-16356)** sandbox escape via use-after-free in the Disability Access APIs component (second instance)
- **[CVE-2026-16357](https://www.cve.org/CVERecord?id=CVE-2026-16357)** incorrect boundary conditions in the Graphics component
- **[CVE-2026-16360](https://www.cve.org/CVERecord?id=CVE-2026-16360)** memory safety bugs shared across ESR 115.38, ESR 140.13, and Firefox 153
- **[CVE-2026-16361](https://www.cve.org/CVERecord?id=CVE-2026-16361)** memory safety bugs shared across ESR 115.38 and ESR 140.13
- **[CVE-2026-16362](https://www.cve.org/CVERecord?id=CVE-2026-16362)** use-after-free in the WebRTC: Audio/Video component
- **[CVE-2026-16363](https://www.cve.org/CVERecord?id=CVE-2026-16363)** JIT miscompilation in the JavaScript: WebAssembly component
- **[CVE-2026-16368](https://www.cve.org/CVERecord?id=CVE-2026-16368)** incorrect boundary conditions in the JavaScript: WebAssembly component
- **[CVE-2026-16369](https://www.cve.org/CVERecord?id=CVE-2026-16369)** integer overflow in the JavaScript: WebAssembly component
- **[CVE-2026-16412](https://www.cve.org/CVERecord?id=CVE-2026-16412)** memory safety bugs shared across ESR 140.13 and Firefox 153

Moderate severity:

- **[CVE-2026-16358](https://www.cve.org/CVERecord?id=CVE-2026-16358)** site isolation issue in the Graphics: WebRender component
- **[CVE-2026-16359](https://www.cve.org/CVERecord?id=CVE-2026-16359)** incorrect boundary conditions in the Audio/Video: GMP component
- **[CVE-2026-16371](https://www.cve.org/CVERecord?id=CVE-2026-16371)** privilege escalation in the DOM: Navigation component
- **[CVE-2026-16374](https://www.cve.org/CVERecord?id=CVE-2026-16374)** information disclosure in the DevTools: Framework component
- **[CVE-2026-16375](https://www.cve.org/CVERecord?id=CVE-2026-16375)** site isolation issue in the Networking: HTTP component
- **[CVE-2026-16377](https://www.cve.org/CVERecord?id=CVE-2026-16377)** mitigation bypass in the PDF Viewer component
- **[CVE-2026-16379](https://www.cve.org/CVERecord?id=CVE-2026-16379)** privilege escalation in the DOM: Content Processes component
- **[CVE-2026-16381](https://www.cve.org/CVERecord?id=CVE-2026-16381)** same-origin policy bypass in the Networking: DNS component
- **[CVE-2026-16383](https://www.cve.org/CVERecord?id=CVE-2026-16383)** mitigation bypass in the DOM: Networking component
- **[CVE-2026-16387](https://www.cve.org/CVERecord?id=CVE-2026-16387)** site isolation issue in the Networking component
- **[CVE-2026-16390](https://www.cve.org/CVERecord?id=CVE-2026-16390)** mitigation bypass in the Enterprise Policies component
- **[CVE-2026-16391](https://www.cve.org/CVERecord?id=CVE-2026-16391)** information disclosure in the Storage: IndexedDB component
- **[CVE-2026-16396](https://www.cve.org/CVERecord?id=CVE-2026-16396)** privilege escalation in WebExtensions

Low severity:

- **[CVE-2026-16405](https://www.cve.org/CVERecord?id=CVE-2026-16405)** information disclosure in the Networking: WebSockets component

---

## [140.12.0] (17/June/2026)

⛐ It's the "twenty-nine CVEs but who's counting" release!

🔄 Updated to Firefox ESR 140.12.0.

🛡️ Addressed 29 CVEs from Mozilla Foundation Security Advisory 2026-58 (June 16, 2026). No critical severity, no active exploitation reported; though this is the heaviest patch cycle in the 140.x series so far: 12 high-severity patches including four separate sandbox escapes and a JIT miscompilation, 15 moderate, 2 low.

High severity:
- **[CVE-2026-12289](https://www.cve.org/CVERecord?id=CVE-2026-12289)** privilege escalation in the Graphics: WebRender component
- **[CVE-2026-12290](https://www.cve.org/CVERecord?id=CVE-2026-12290)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12291](https://www.cve.org/CVERecord?id=CVE-2026-12291)** use-after-free in the Networking: HTTP component
- **[CVE-2026-12292](https://www.cve.org/CVERecord?id=CVE-2026-12292)** incorrect boundary conditions in the Web Audio component
- **[CVE-2026-12294](https://www.cve.org/CVERecord?id=CVE-2026-12294)** sandbox escape in the DOM: Workers component
- **[CVE-2026-12295](https://www.cve.org/CVERecord?id=CVE-2026-12295)** sandbox escape in the DOM: Navigation component
- **[CVE-2026-12296](https://www.cve.org/CVERecord?id=CVE-2026-12296)** sandbox escape in the Security: Process Sandboxing component
- **[CVE-2026-12297](https://www.cve.org/CVERecord?id=CVE-2026-12297)** sandbox escape via incorrect boundary conditions in the Networking component
- **[CVE-2026-12298](https://www.cve.org/CVERecord?id=CVE-2026-12298)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12299](https://www.cve.org/CVERecord?id=CVE-2026-12299)** JIT miscompilation in the DOM: Core & HTML component
- **[CVE-2026-12328](https://www.cve.org/CVERecord?id=CVE-2026-12328)** memory safety bugs shared across ESR 115.37, ESR 140.12, and Firefox 152 (evidence of memory corruption, plausible RCE potential)
- **[CVE-2026-12329](https://www.cve.org/CVERecord?id=CVE-2026-12329)** memory safety bug in Firefox ESR 140.12

Moderate severity:
- **[CVE-2026-12302](https://www.cve.org/CVERecord?id=CVE-2026-12302)** mitigation bypass in the DOM: Security component
- **[CVE-2026-12304](https://www.cve.org/CVERecord?id=CVE-2026-12304)** same-origin policy bypass in the Networking: Cookies component
- **[CVE-2026-12305](https://www.cve.org/CVERecord?id=CVE-2026-12305)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12306](https://www.cve.org/CVERecord?id=CVE-2026-12306)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12307](https://www.cve.org/CVERecord?id=CVE-2026-12307)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12308](https://www.cve.org/CVERecord?id=CVE-2026-12308)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12309](https://www.cve.org/CVERecord?id=CVE-2026-12309)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12310](https://www.cve.org/CVERecord?id=CVE-2026-12310)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12311](https://www.cve.org/CVERecord?id=CVE-2026-12311)** information disclosure + sandbox escape in the Security: Process Sandboxing component
- **[CVE-2026-12312](https://www.cve.org/CVERecord?id=CVE-2026-12312)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12313](https://www.cve.org/CVERecord?id=CVE-2026-12313)** information disclosure + sandbox escape in the Security: Process Sandboxing component
- **[CVE-2026-12314](https://www.cve.org/CVERecord?id=CVE-2026-12314)** memory safety bug in Firefox ESR 140.12
- **[CVE-2026-12315](https://www.cve.org/CVERecord?id=CVE-2026-12315)** mitigation bypass in the DOM: Security component
- **[CVE-2026-12327](https://www.cve.org/CVERecord?id=CVE-2026-12327)** memory safety bugs shared across ESR 140.12 and Firefox 152 (evidence of memory corruption, plausible RCE potential)
- **[CVE-2026-12330](https://www.cve.org/CVERecord?id=CVE-2026-12330)** incorrect boundary conditions in the Internationalization component

Low severity:
- **[CVE-2026-12324](https://www.cve.org/CVERecord?id=CVE-2026-12324)** incorrect boundary conditions in the Graphics: CanvasWebGL component
- **[CVE-2026-12325](https://www.cve.org/CVERecord?id=CVE-2026-12325)** denial-of-service in the Graphics: ImageLib component

---

## [140.11.0] (19/May/2026)

⛐ It's the "stay in the sandbox" release! 

🔄 Updated to Firefox ESR 140.11.0.

🛡️ Addressed 15 CVEs from Mozilla Foundation Security Advisory 2026-48 (May 19, 2026). No critical issues, no active exploitation reported.

High severity:

- **[CVE-2026-8401](https://www.cve.org/CVERecord?id=CVE-2026-8401)** sandbox escape via the Profile Backup component
- **[CVE-2026-8947](https://www.cve.org/CVERecord?id=CVE-2026-8947)** use-after-free in WebIDL bindings
- **[CVE-2026-8388](https://www.cve.org/CVERecord?id=CVE-2026-8388)** out-of-bounds read in the JIT compiler
- **[CVE-2026-8391](https://www.cve.org/CVERecord?id=CVE-2026-8391)** issue in the JavaScript engine
- **[CVE-2026-8946](https://www.cve.org/CVERecord?id=CVE-2026-8946)** out-of-bounds read in Web Codecs

Moderate severity:

- **[CVE-2026-8953](https://www.cve.org/CVERecord?id=CVE-2026-8953)** sandbox escape via use-after-free in Accessibility APIs
- **[CVE-2026-8958](https://www.cve.org/CVERecord?id=CVE-2026-8958)** info disclosure + sandbox escape in process sandboxing
- **[CVE-2026-8959](https://www.cve.org/CVERecord?id=CVE-2026-8959)** sandbox escape via out-of-bounds read in Win32 widgets
- **[CVE-2026-8950](https://www.cve.org/CVERecord?id=CVE-2026-8950)** same-origin policy bypass in HTTP networking
- **[CVE-2026-8949](https://www.cve.org/CVERecord?id=CVE-2026-8949)** integer overflow in Win32 widgets
- **[CVE-2026-8956](https://www.cve.org/CVERecord?id=CVE-2026-8956)** integer overflow in JAR networking
- **[CVE-2026-8955](https://www.cve.org/CVERecord?id=CVE-2026-8955)** privilege escalation in DOM Workers
- **[CVE-2026-8957](https://www.cve.org/CVERecord?id=CVE-2026-8957)** privilege escalation in Enterprise Policies
- **[CVE-2026-8954](https://www.cve.org/CVERecord?id=CVE-2026-8954)** out-of-bounds read in audio/video processing

Low severity:

- **[CVE-2026-8961](https://www.cve.org/CVERecord?id=CVE-2026-8961)** spoofing issue in Form Autofill

---

## [140.10.2] (10/May/2026)

⛐ It's the "patch Tuesday came early" release!

🔄 Updated to Firefox ESR 140.10.2.

🛡️ Addressed three high-severity CVEs from Mozilla Foundation Security Advisory 2026-41 (May 7, 2026): [CVE-2026-8090](https://www.cve.org/CVERecord?id=CVE-2026-8090) (use-after-free in the DOM/networking component), [CVE-2026-8094](https://www.cve.org/CVERecord?id=CVE-2026-8094) (issue in the WebRTC component), and [CVE-2026-8092](https://www.cve.org/CVERecord?id=CVE-2026-8092) (memory safety bugs with plausible RCE potential, shared across ESR 115.35.2, 140.10.2, and Firefox 150.0.2). Nothing critical this cycle (no sandbox escapes, no active exploitation reported), but the memory safety batch alone is reason enough to ship.

🧠 This is the 8th PGO training refinement. Three iterations this release focused on automating the corpus run end-to-end. Turns out auto-fullscreen on video sites is genuinely cursed... ad timing is inconsistent enough across YouTube, Twitch, and DailyMotion that any reliable automation would need per-site ad-skip logic and timing jitter I don't want to maintain. Fullscreen clicks are manual for now, which is fine; the duck doesn't care who clicked the button, only that the video codec paths got exercised.

---

## [140.10.1] (29/April/2026)

⛐ It's the "memory corruption and really long build days" release:

🔄 Updated to Firefox ESR 140.10.1.

🛡️ Addressed [CVE-2026-7321](https://www.cve.org/CVERecord?id=CVE-2026-7321) (WebRTC sandbox escape, CVSS 9.6; the one that actually prompted the point release), [CVE-2026-7322](https://www.cve.org/CVERecord?id=CVE-2026-7322) (memory safety bugs with plausible RCE potential across ESR 115/140 and Firefox 150), and [CVE-2026-7323](https://www.cve.org/CVERecord?id=CVE-2026-7323) (additional memory safety bugs in ESR 140.10.0 and Firefox 150). Mozilla Foundation Security Advisory 2026-36. The WebRTC one had "critical" written all over it; good patch cycle to stay current on.

🧠 This is the 5th build using the custom PGO training infrastructure. The extension now drives 87 sites through realistic scroll patterns, video playback, SPA hydration, map interactions, and speed tests before handing off to a clean shutdown. Each training run clocks in around 121 minutes. Each full build is around 190 minutes. The duck is very well trained at this point.

🗜️ Retired UPX compression on the installer stub entirely. UPX 5.x triggered Malwarebytes AI false positives at every compression level tested; including -1. Not worth the 66KB. Zero VirusTotal flags on both files this release.

🔧 Committed the custom PGO and UPX patches to the branch so they survive rebases automatically. Future releases won't require the manual patch dance that this one did.

---

## [140.10.0] (21/April/2026)

⛐ It's the "the duck went to the gym" release:

🔄 Updated to Firefox ESR 140.10.0. Picked up today's upstream security patch.

🛡️ Patched 13 high-severity CVEs from MFSA 2026-32 (April 21, 2026). Highlights: use-after-free in the DOM ([CVE-2026-6746](https://www.cve.org/CVERecord?id=CVE-2026-6746)), use-after-free in WebRTC ([CVE-2026-6747](https://www.cve.org/CVERecord?id=CVE-2026-6747)), uninitialized memory in Web Codecs ([CVE-2026-6748](https://www.cve.org/CVERecord?id=CVE-2026-6748)/[CVE-2026-6751](https://www.cve.org/CVERecord?id=CVE-2026-6751)), privilege escalation in WebRender ([CVE-2026-6750](https://www.cve.org/CVERecord?id=CVE-2026-6750)), use-after-free in the JS engine ([CVE-2026-6754](https://www.cve.org/CVERecord?id=CVE-2026-6754)), and a broad set of memory safety bugs with plausible RCE potential ([CVE-2026-6785](https://www.cve.org/CVERecord?id=CVE-2026-6785)/[CVE-2026-6786](https://www.cve.org/CVERecord?id=CVE-2026-6786)). Full advisory: https://www.mozilla.org/en-US/security/advisories/mfsa2026-32/

🧠 Rebuilt the PGO training infrastructure from scratch as a proper WebExtension. The extension drives all 87 sites autonomously through scroll behaviors, video playback, SPA hydration, map panning, and speed tests, then navigates to a localhost-served shutdown page that calls Quitter.quit() for a clean profraw flush. This is the 5th refinement build using custom training, with improved tunings after each run.

🦾 Added RUSTFLAGS="-C target-cpu=znver5 -C opt-level=3" (Zen 5) and "-C target-cpu=haswell -C opt-level=3" (Legacy). The Rust side of the build was previously compiling to a generic target; it's now CPU-tuned to match the C/C++ flags.

🖳 Switched the Legacy build to -march=x86-64-v3 -mtune=generic. Covers Intel Haswell (2013) and later, and most AMD chips from Excavator (2015) onward. The generic tune keeps it fast across both vendors.

🔧 Patched profileserver.py with a 3-hour watchdog thread (safety net if a training site hangs), a @response_file workaround for Windows' 32K command-line limit when llvm-profdata merge chokes on hundreds of profraw filenames, and a Speedometer 3 HTTP server on port 8000 alongside the existing port 8888 server.

🚫 Disabled the updater, maintenance service, default-browser-agent, and crashreporter at compile time. None of them are used, and they were just sitting there consuming memory and storage for no reason.

🧪 Tested --enable-optimize="-O3" and --enable-optimize="-O3 /Gy". Both caused lld-link duplicate symbol errors in mozglue during the PGO instrumented phase; -O3 as a bare flag replaces Mozilla's default flag expansion in a way that breaks jemalloc operator handling. Reverted to bare --enable-optimize. Documented here so I remember not to try this again.

🗜️ Upgraded UPX from 3.95w (2018) to 5.1.1 (2026). No meaningful size change, but years of fixes baked in. Turns out 5.x's defaults (--best --lzma --ultra-brute) are spicy enough to turn two VirusTotal flags into six, so I patched exe_7z_archive.py to dial it back to -6 with no algorithm flags. That added 1-2MB more total filesize, but there are no more false positives from VirusTotal.

⏱️ Fun facts: each PGO run alone takes ~112 minutes, and a complete build now clocks in at ~190 minutes. (pls send RAM & caffeine)

🤖 Fun fact # 2 (3?): I spent a painful number of Claude Opus 4.6 credits on this release, and Anthropic waited until I was basically done to drop Opus 4.7; which uses over a third fewer tokens per task. I'm not saying the timing was personal. I'm just saying the timing was personal.

---

## [140.9.1] (09/April/2026)

⛐ It's the "security patch, everyone's welcome!" release:

🔄 Updated to Firefox ESR 140.9.1. Just Mozilla patching things that needed patching.

🍾 First Skylake and newer release! Download the Legacy version if you don't have a AMD Zen 5 CPU. This build is compiled with:
-march=skylake -mtune=skylake
It requires a CPU with AVX2, BMI1, BMI2, FMA, LZCNT, MOVBE, and POPCNT support.
In practice that covers most Intel chips from Broadwell (2014) onward and most AMD chips from Excavator (2015) onward.

🛡️ Addressed three high-severity CVEs from Mozilla Foundation Security Advisory 2026-27 (April 7, 2026): [CVE-2026-5732](https://www.cve.org/CVERecord?id=CVE-2026-5732) (integer overflow in text rendering), [CVE-2026-5731](https://www.cve.org/CVERecord?id=CVE-2026-5731) (memory safety bugs shared across ESR 115.34.0/140.9.0/Firefox 149.0.1), and [CVE-2026-5734](https://www.cve.org/CVERecord?id=CVE-2026-5734) (memory safety bugs in ESR 140.9.0/Firefox 149.0.1). Two of the three showed evidence of memory corruption with plausible RCE potential.

🚨 VirusTotal: two flags (Arctic Wolf, Jiangmin) on Setup.exe; same compression heuristic suspects as always. Standalone clean.

---

## [140.9.0] (25/March/2026)

⛐ It's the "homework turned in on time" release:

🔄 Updated to Firefox ESR 140.9.0 release build (stable over latest-available).

🎂 Synchronized release date with Mozilla's ESR cadence; now shipping same-day as upstream ESR.

🛡️ AV false positive heads-up: compression flags (higher compression + file breakup) trigger suspicious-file detections on some scanners. Passed local Windows AV. VirusTotal: one flag (Jiangmin).

👩🏼‍🏫  Noted: custom PGO training scripts are coming. The duck will waddle faster. (coming soon™️)

---

## [140.8.0_PGO] (14/February/2026)

⛐ It's the "my bad, PGO was off!" release:

🔄 Updated to latest upstream ESR 140.x files.

🧠 Rebuilt with PGO correctly enabled; previous build had the flag silently missing.

🧹 Removed ccache; conflicts with PGO builds; user performance wins over compile time.

🗜️ Compressed Setup.exe further with additional UPX flags (`--best`, `--lzma`, `--ultra-brute`).

🛡️ AV heads-up: aggressive compression triggers scanner heuristics. Passed local Bitdefender. VirusTotal: two flags (Arctic Wolf, Jiangmin).

---

## [140.8.0] (31/January/2026)

⛐ It's the "I DID A THING!" release:

🌐 Renamed Nightly to Ryfox.

😐  Renamed Ryfox to ducksteps in accordance with Mozilla naming recommendations.

🏞️ Created an icon set via ChatGPT and implemented it in installer and browser. Not an artist; just wanted something welcoming and scalable. Proper iconography is a future problem.

💾 Moved working directories to ReFS storage for faster builds from source.

🚄 Configured ccache for faster compiling.

🐞 Patched numerous minor compilation bugs.

🪨 Swapped codebase from Nightly to ESR (major updates every 6;12 months, monthly security/bugfix cadence). More stable, easier to keep on a normal release schedule.

🗜️ Compressed standalone 7z as much as possible. (Level 9 Ultra, LZMA2, 3840 MB dict, 273 word size, solid block, 3 threads)

🤷🏽‍♂️ Unable to compress Setup.exe further; the two files ended up within 2.65 MB of each other.

💯 Version numbering now matches compiled Firefox version going forward.

---

## [v1.0.0] (09/December/2025)

Initial alpha release. Shipped as "Ryfox 1.0.0."

🦊  Built on Firefox Nightly 142.0a1 (2025-12-08).

🧰  Toolchain: VS 2022 Build Tools 17.14.36717.8, Rustup 1.28.2, Python 3.14.2, Chocolatey 2.6.0, ccache 4.12.2.

Benchmarks (9950X3D / RTX 4080 Super / 48GB DDR5 / 1080p 60Hz):

- Speedometer 3.1: 35.5

- JetStream 2.2: 336.123

- MotionMark 1.3.1: 2136.29

- Speedometer 2.1: 624
