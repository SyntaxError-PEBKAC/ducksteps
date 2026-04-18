## 🚀 Why ducksteps is faster than stock Firefox

Mozilla ships a build of Firefox that runs on basically every x86-64 PC made in the last 15 years. That's great for compatibility. It's not great for performance. ducksteps is compiled specifically to go faster on the hardware it targets, using every tool available.

Here's what changed and why it matters:

---

- ⚙️ **Optimized build (`--enable-optimize`)**  
  Compiler optimizations turned all the way up. Faster code execution, snappier UI, smoother scrolling on heavy pages.

- 🗜️ **Full LTO (Link-Time Optimization) (`--enable-lto=full`)**  
  Normally the compiler optimizes each file in isolation. Full LTO lets it see the entire browser at once and eliminate wasted work across the whole codebase. Tighter hot paths, better cache behavior, fewer micro-pauses.

- 🧪 **PGO (Profile-Guided Optimization) (`MOZ_PGO=1`)**  
  Before the final build compiles, Firefox runs a training session. It browses real websites and records which code runs most often. The compiler uses that data to make *those specific paths* as fast as possible. Faster startup, smoother tab switching, less hitching on page load.

- 🏋️ **Custom PGO training corpus (80+ sites, ~112 minutes)**  
  Stock Firefox trains PGO on a generic Mozilla workload. ducksteps trains on 80+ real websites — including YouTube, Reddit, news sites, maps, e-commerce, and speed tests — with realistic scroll behavior, video playback, and SPA navigation simulated automatically. Better training data means the optimization is tuned to how browsers actually get used, not a lab benchmark. ducksteps is the result of multiple refinement iterations with timing improvements from live monitoring of previous runs.

- 🛠️ **Clang toolchain + LLD linker (`clang-cl`, `lld-link`)**  
  The full LLVM toolchain throughout — no MSVC codegen. Pairs tightly with LTO and PGO for stronger whole-program results and more consistent output.

- 🎯 **CPU-specific tuning — C/C++ and Rust**  
  Stock Firefox targets a generic x86-64 baseline that runs everywhere. ducksteps targets your CPU specifically:
  - **Zen 5 build:** `-march=znver5 -mtune=znver5` + `RUSTFLAGS="-C target-cpu=znver5"` — every instruction optimized for Ryzen 9000 / Ryzen AI 300 silicon, including the Rust components (WebRender, the style engine, parts of the networking stack)
  - **Legacy build:** `-march=x86-64-v3 -mtune=generic` + `RUSTFLAGS="-C target-cpu=haswell"` — targets the full AVX2 feature set without locking to one microarchitecture, so it runs fast on both Intel (Haswell 2013+) and AMD (Excavator 2015+) hardware
  
  CPU-specific code generation means the browser can use instruction sets and optimizations that the generic build leaves on the table.

- 🚀 **Release mode (`--enable-release`)**  
  Production build settings, not developer build settings. Avoids overhead that's only useful when you're debugging Firefox itself.

- 🪓 **Debug mode stripped (`--disable-debug`)**  
  Developer logging and runtime checks removed. Less background work, fewer micro-pauses on heavy pages.

- 🔇 **Unused services removed at compile time**  
  The updater, maintenance service, default-browser agent, and crash reporter are all compiled out entirely — not just disabled in settings. ducksteps manages its own update cadence, doesn't phone home, and doesn't need Mozilla's background services running. Smaller binary (~5–9 MB), lower RAM floor (~4–9 MB less resident memory), no periodic background wake-ups, and less security risk.

---

## 🧰 Build consistency

- 🧱 **Unified build (`--enable-unified-build`)**  
  Faster compile times — I can iterate and ship security updates faster.

- 📦 **Everything built locally (`--disable-artifact-builds`)**  
  No mixing prebuilt Mozilla pieces with locally-optimized ones. One coherent build, start to finish.
