# 📋 System requirements and the build check

The short version lives in the [README](../README.md). This page has the details: which CPUs run which build, what the PowerShell check actually does, and where it can be wrong.

## 🖥️ Operating system

Windows 11 (x64). Windows 10 and earlier are untested and may or may not work. Windows on ARM isn't supported.

## 🧩 CPU: which build runs where

Every release comes in two builds. The label in the file name tells you which one you're looking at:

| Label in the file name | Compiled for | Runs on |
|---|---|---|
| **`.AVX512.`** (Zen 5) | `-march=znver5` | AMD Zen 5 only: Ryzen 9000 series, Ryzen AI 300 / AI Max series, Threadripper 9000 / PRO 9000 series, EPYC 4005 / 9005 series |
| **`.Legacy.`** (AVX2) | `-march=x86-64-v3` | Most Intel chips from Haswell (2013) onward, most AMD chips from Excavator (2015) onward, and every Ryzen ever made (Zen 5 included) |

⚠️ "AVX512" in the file name means "the Zen 5 build," not "any CPU with AVX-512." It's compiled for Zen 5's exact instruction set, which other AVX-512 chips don't match. Ryzen 7000 and 8000 (Zen 4), for example, have AVX-512 but lack AVX-VNNI, which the Zen 5 build uses throughout video and audio decoding. Those chips need Legacy. There's no Intel equivalent of the Zen 5 build.

🖳 Budget Intel chips are the main Legacy exception: many Pentium, Celeron, and Atom models from before 2021 have no AVX2 and can't run either build.

## 🔍 What the PowerShell check does

The one-line check in the README reads your CPU's name, family, and model from the registry (`HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0`), then asks Windows whether AVX-512 and AVX2 are usable through `IsProcessorFeaturePresent` in kernel32. That also confirms Windows has those instructions switched on, not just that the silicon has them.

In PowerShell 7 it goes further on AMD chips: it reads the CPU's own feature list (`CPUID`) and checks for every instruction set the Zen 5 build's compiler settings allow.

Nothing is installed, changed, or sent anywhere. Windows PowerShell 5.1 briefly writes a temp file while compiling the one-line helper, then deletes it. The check works in both the built-in Windows PowerShell 5.1 and PowerShell 7.

You'll get your CPU name and one of three answers: **the .AVX512. files**, **the .Legacy. files**, or **neither will run here**.

## ⚖️ Limitations, plainly

🖳 The Legacy answer checks AVX2 and assumes the rest of the x86-64-v3 set (BMI1, BMI2, F16C, FMA, LZCNT, MOVBE). Every real CPU with AVX2 has all of those; a virtual machine that hides some CPU features can fool it.

🧬 In Windows PowerShell 5.1, the Zen 5 answer relies on a list of Zen 5 model numbers taken from the Linux kernel's own CPU table (as of August 2026), because 5.1 can't read the full feature list. Newer AMD chips get Legacy there, plus a tip to re-run the check in PowerShell 7.

🔬 In PowerShell 7, a chip newer than Zen 5 that reports every required instruction set gets the Zen 5 build, with a note that it's untested. The check skips a handful of system-level instructions the compiler never generates on its own. It also skips three Zen 5 additions (MOVDIRI, MOVDIR64B, and PREFETCHI) that Windows' built-in virtualization-based security hides from programs even on real Zen 5 chips; current releases contain none of them. A CPU or hypervisor that misreports other features can still fool it.

🔒 Some work or school PCs block the `Add-Type` command. If you get a wall of red text, check manually instead: find your CPU name (Task Manager → Performance → CPU, top right) and compare it to the table above, or look for AVX2 in CPU-Z's Instructions field.
