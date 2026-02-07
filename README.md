ducksteps for Windows 11

Zen 5 compiled web browser with PGO/LTO for AMD Ryzen 9000, Ryzen AI 300, Threadripper PRO 9000, and Epyc 9005 series CPUs.

Google discontinuing manifest v2 support, combined with oauth2 issues in Chromium forced me to stop using my favorite browser (Chromium_Clang) and make this Firefox fork.

This is the first thing I have ever compiled in to something I could share, and I am EXTREMELY inexperienced. Starting with a web browser might not have been the best "Hello World" project, but I really wanted a browser that fully utilized my 9950X3D CPU in Windows and I hope that is what I am accomplishing.

I relied HEAVILY on ChatGPT to get me across both the start AND finish line, and would welcome human advice if there's something I messed up on.

Download links for both the installer and standalone version are on the Releases page (right side of screen).

***Nerdy notes:

**Tested on AMD 9950X3D CPU, RTX 4080 Super GPU, 48GB DDR5, Windows 11

**Version 1.0.0 benchmarks
- Speedometer 3.1: 35.5
- Jetstream 2.2: 336.123
- MotionMark 1.3.1 (1080p 60hz RTX 4080 Super): 2136.29
- https://thorium.rocks/misc/Speedometer_2.1 : 624

**I DON'T KNOW WHAT I AM DOING!!! Here's my full ChatGPT source for proof:
- https://chatgpt.com/share/693857f1-d584-8013-a456-19b86473cba1

**Sourcebase:
https://github.com/mozilla-firefox/firefox

**Build & Test Tools:
- Windows 11
- Mozilla Build
- Git
- LLVM
- Vulkan SDK
- Visual Studio 2022 Build Tools
- Rustup
- Python
- Chocolatey
- ccache
- Firefox ESR (64-bit)

**Todo List:

- Automate the build, compression, & upload process further.
- Replace setup/uninstaller icons.
- Create better icon imageset.
- Make the duck waddle even faster?


**Legal Mumbo Jumbo
- ducksteps is an unofficial build. “Firefox” and Mozilla logos are Mozilla trademarks; ducksteps is not affiliated with or endorsed by Mozilla.
