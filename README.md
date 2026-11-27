# 🦆 ducksteps

A custom Windows build of Firefox ESR, compiled from source with Zen 5 or AVX2 CPU tuning, full LTO, and tuned PGO enabled.

## 🤔 Why ducksteps exists

Chrome-based browsers stopped letting uBlock Origin work fully, and my Google login workarounds broke in the Chromium build I used (Chromium_Clang). In Firefox, ad blocking works fully and I can log in to Google services, but Mozilla's official build is made to run on nearly any PC from the last 15 years, leaving a lot of a newer CPU's speed unused. So I rebuilt Firefox for more *SPEED*:

🎯 Built for your CPU: one build uses everything AMD's Zen 5 chips can do, and one targets most PCs from 2013 onward.

🔗 Optimized as one whole program instead of piece by piece (full LTO).

🧠 Tuned by recording how the browser runs on 80+ real websites, then rebuilding around that (PGO).

How that makes it faster: [Why use ducksteps](Docs/Why%20use%20ducksteps.md). Build it yourself: [Building.md](Docs/Building.md).

## 📊 Benchmarks (Zen 5 build vs. stock Firefox ESR 140.11.0)

Tested on AMD Ryzen 9950X3D / 48GB DDR5 / RTX 4080 Super / Windows 11 25H2.

ducksteps renders animations and scrolling **~10% faster** than stock Firefox on the same hardware, and handles real-world JavaScript **~2% faster**. It scores ~2% lower on short synthetic microbenchmarks — that's a known, deliberate tradeoff from tuning PGO for real browsing instead of benchmark loops.

Full numbers, methodology, and per-test breakdowns: [PerformanceBenchmark.md](Docs/PerformanceBenchmark.md).

## 📋 Which build do I need?

Windows 11 (x64). **AMD Zen 5** (Ryzen 9000, Ryzen AI 300 / AI Max, Threadripper 9000, EPYC 4005 / 9005): get the `.AVX512.` files. **Most other PCs from 2013 onward:** get the `.Legacy.` files. Not sure? Right-click Start → **Terminal**, paste this, and press Enter:

```powershell
& { $k = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('HARDWARE\DESCRIPTION\System\CentralProcessor\0'); $id = "$($k.GetValue('Identifier'))"; $n = "$($k.GetValue('ProcessorNameString'))".Trim(); $amd = $k.GetValue('VendorIdentifier') -eq 'AuthenticAMD'; if (-not ('DS.Cpu' -as [type])) { Add-Type -Namespace DS -Name Cpu -MemberDefinition '[DllImport("kernel32.dll")] public static extern bool IsProcessorFeaturePresent(uint f);' }; $f = 0; $m = 0; if ($id -match 'Family (\d+) Model (\d+)') { $f = [int]$Matches[1]; $m = [int]$Matches[2] }; $listed = $amd -and $f -eq 26 -and ($m -le 0x2F -or ($m -ge 0x40 -and $m -le 0x4F) -or ($m -ge 0x60 -and $m -le 0x7F) -or ($m -ge 0xD0 -and $m -le 0xD7)); $x = 'System.Runtime.Intrinsics.X86.X86Base' -as [type]; $exact = $amd -and $x -and $x::IsSupported; if ($exact) { $q = { param($l, $s) $x::CpuId([Convert]::ToInt32($l, 16), $s) }; $has = { param($v, $b) @($b | Where-Object { -not ($v -band (1 -shl $_)) }).Count -eq 0 }; $c1 = & $q '1' 0; $c7 = & $q '7' 0; $c71 = & $q '7' 1; $e1 = & $q '80000001' 0; $isa = (& $q '0' 0).Item1 -ge 7 -and $c7.Item1 -ge 1 -and (& $has $c1.Item3 1,9,12,13,19,20,22,23,25,28,29,30) -and (& $has $c7.Item2 3,5,8,16,17,18,19,21,23,24,28,29,30,31) -and (& $has $c7.Item3 1,6,8,9,10,11,12,14,22) -and (& $has $c7.Item4 8) -and (& $has $c71.Item1 4,5) -and (& $has $e1.Item3 0,5,6,8) } else { $isa = $listed }; $zen5 = $isa -and [DS.Cpu]::IsProcessorFeaturePresent(41); Write-Host "`nCPU: $n ($id)"; if ($zen5) { Write-Host 'Download: the .AVX512. files (Zen 5 build)' -ForegroundColor Green; if (-not $listed) { Write-Host 'Note: this chip supports everything the Zen 5 build uses, but it is newer than Zen 5 and untested. If anything misbehaves, use Legacy.' } } elseif ([DS.Cpu]::IsProcessorFeaturePresent(40)) { Write-Host 'Download: the .Legacy. files (AVX2 build)' -ForegroundColor Green; if ($amd -and $f -ge 26 -and -not $exact) { Write-Host 'Tip: this AMD chip might also run the .AVX512. files. Run this check in PowerShell 7 for an exact answer.' } } else { Write-Host 'Neither build will run here: no AVX2 support detected.' -ForegroundColor Red } }
```

Full CPU lists, edge cases (Zen 4 has AVX-512 but still needs Legacy), and what that command does: [Requirements.md](Docs/Requirements.md).

## 📥 Download

Grab the right installer or portable .7z from the [Releases page](https://github.com/SyntaxError-PEBKAC/ducksteps/releases).

`ducksteps.X.X.X.AVX512.Setup.exe` — Zen 5 Installer — installs like a normal app

`ducksteps.X.X.X.AVX512.Standalone.7z` — Zen 5 Portable — extract and run, no installation

`ducksteps.X.X.X.Legacy.Setup.exe` — Legacy Installer — installs like a normal app

`ducksteps.X.X.X.Legacy.Standalone.7z` — Legacy Portable — extract and run, no installation

Windows 11 (23H2 and newer) can extract .7z files on its own (right-click → Extract All); no 7-Zip needed.

SHA512 hashes, GitHub's own SHA256 digests (shown next to each file on the release page), and VirusTotal results are included with every release. The installers aren't code-signed, so Windows SmartScreen may warn the first time you run one. How to check a download, and what protects each release: [Security.md](Docs/Security.md).

## 🔔 Update notifications

ducksteps doesn't update itself. Once a day it asks GitHub whether a newer version exists and, if so, shows a bar with a link. GitHub sees your IP address and browser version, the same as any visit; I get none of it. Details and how to turn it off: [Security.md](Docs/Security.md#built-in-browser-features).

## ⚖️ Legal

ducksteps is an unofficial build. "Firefox" and the Firefox logo are trademarks of Mozilla. ducksteps is not affiliated with or endorsed by Mozilla.

Source: [mozilla-firefox/firefox](https://github.com/mozilla-firefox/firefox). Licensed under MPL 2.0.

## 🤷 Honest notes

This is the first thing I've ever compiled into something I could share, and I am extremely inexperienced. Starting with a web browser was probably not the smartest "Hello World" project, but I wanted a browser that fully utilized my 9950X3D and this is what I ended up with. I hope you enjoy it!

I relied heavily on ChatGPT and Claude to get across both the start and finish lines. Human feedback is always welcome — open an [issue](https://github.com/SyntaxError-PEBKAC/ducksteps/issues/new) or hit the [Discussions tab](https://github.com/SyntaxError-PEBKAC/ducksteps/discussions).
