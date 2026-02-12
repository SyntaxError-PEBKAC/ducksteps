## 🚀 End-user performance & experience improvements

- ⚙️ **Optimized build (`--enable-optimize`)**
  - Faster code execution → snappier UI and page rendering
  - Smoother scrolling on heavy sites
  - Better efficiency under lots of tabs

- 🗜️ **Full LTO (Link-Time Optimization) (`--enable-lto=full`)**
  - Optimizes across the whole browser, not just file-by-file
  - Improves hot paths (rendering, graphics, JS glue) by trimming wasted work
  - Can improve smoothness by helping CPU cache behavior

- 🧪 **PGO (Profile-Guided Optimization) (`MOZ_PGO=1`)**
  - “Trains” optimizations using real browsing-like workloads
  - Often improves startup + “first moments after launch”
  - Helps reduce stutters in common actions (opening tabs, switching, navigation)

- 🛠️ **Clang toolchain + LLD linker (`clang-cl`, `lld-link`)**
  - Frequently produces more optimized Windows binaries
  - Pairs well with LTO/PGO for stronger whole-program results
  - Can improve consistency (fewer edge-case slowdowns from suboptimal linking)

- 🎯 **Zen 5 tuning (`-march=znver5 -mtune=znver5`)**
  - Generates CPU-specific code instead of “one-size-fits-all”
  - Can boost performance on CPU-heavy browsing (script-heavy sites, layout)
  - Better throughput can mean less hitching under multitasking

- 🚀 **Release mode (`--enable-release`)**
  - Uses production-grade build settings intended for performance
  - Avoids “developer build” overhead that can subtly slow things down
  - More consistent real-world behavior

- 🪓 **Debug disabled (`--disable-debug`)**
  - Removes dev-only checks/logging that can add runtime overhead
  - Less background work → fewer micro-pauses (jank)
  - Can reduce CPU usage on busy pages (often helps battery/fan noise)

## 🧰 Build/compile workflow & consistency

- 🧱 **Unified build (`--enable-unified-build`)**
  - Faster compile times → I can iterate and ship updates faster
  - Makes performance/security update cadence easier to sustain

- 📦 **No artifact builds (`--disable-artifact-builds`)**
  - Everything built locally → more consistent “one coherent build”
  - Avoids mixing prebuilt pieces that might not match your optimization choices