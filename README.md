Ryfox for Windows 11

Zen 5 compiled web browser for AMD 9950X3D (May work on similar 9000 series CPUs).


Google discontinuing manifest v2 support, combined with oauth2 issues in Chromium forced me to stop using my favorite browser (Chromium_Clang) and make this Firefox fork.

This is the first thing I have ever compiled in to something I could share, and I am EXTREMELY inexperienced. Starting with a web browser might not have been the best "Hello World" project, but I really wanted a browser that fully utilized my 9950X3D CPU in Windows and I hope that is what I am accomplishing.

I relied HEAVILY on ChatGPT to get me across both the start AND finish line, and would welcome human advice if there's something I messed up on.


***Nerdy notes:

Tested on AMD 9950X3D CPU, RTX 4080 Super GPU, 48GB DDR5, Windows 11


**Ryfox 1.0.0 benchmarks

Speedometer 3.1: 35.5

Jetstream 2.2: 336.123

MotionMark 1.3.1 (1080p 60hz RTX 4080 Super): 2136.29

https://thorium.rocks/misc/Speedometer_2.1 : 624


**I DON'T KNOW WHAT I AM DOING!!! ChatGPT source for proof:

https://chatgpt.com/share/693857f1-d584-8013-a456-19b86473cba1


**Source base:

https://github.com/mozilla/gecko-dev @ `5836a062726f715fda621338a17b51aff30d0a8c`


**Build config (.mozconfig):

- `--enable-application=browser`
- `--enable-release`
- `--disable-debug`
- `--enable-optimize`
- `--enable-lto=full`
- `--disable-artifact-builds`
- `MOZ_PGO=1`
- `--with-ccache`
- `CC/CXX=clang-cl`
- `LINKER/HOST_LINKER=lld-link`
- `CFLAGS/CXXFLAGS=-march=znver5 -mtune=znver5 -ffp-contract=fast -funroll-loops -fomit-frame-pointer`


**Build & Test Tools:

Windows 11

Mozilla Build

Git

LLVM

Vulkan SDK

Visual Studio 2022 Build Tools

Rustup

Python

Chocolatey

ccache

Firefox Nightly(64-bit)


**Todo (Though I'm just happy/relieved/anxious it runs at all at the moment lol!):

Rename Nightly to Ryfox.

Compress EXE further with 7zip commands.

Create icon image.

Customize installer EXE text and images.

Move source codebase to REFS storage on my PC for faster builds.

Figure out a release schedule if there is any interest in the project.

Automate build. compression, & upload process.

Make the fox go even faster?


**Legal


Ryfox is an unofficial build. “Firefox” and Mozilla logos are Mozilla trademarks; Ryfox is not affiliated with or endorsed by Mozilla.
