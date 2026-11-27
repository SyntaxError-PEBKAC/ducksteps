# Security

How ducksteps releases are built and published, how to check that a download is the file I published, and how to report a problem. This lists only what is in place today, plus the limits. Last reviewed: 2026-11-25.

## Verifying downloads

Download only from the [Releases page](https://github.com/SyntaxError-PEBKAC/ducksteps/releases). Every release lists a SHA512 hash and a VirusTotal link for each file. Checks, in order (PowerShell shown):

1. **SHA512 (from the release notes).** Compare the output with the hash listed for your file:

   ```powershell
   Get-FileHash -Algorithm SHA512 .\ducksteps.153.8.0.AVX512.Setup.exe
   ```

2. **SHA256 (from GitHub).** GitHub computes its own SHA256 digest for every uploaded file and shows it next to the file on the release page. I don't type that one, so it is an independent cross-check:

   ```powershell
   Get-FileHash -Algorithm SHA256 .\ducksteps.153.8.0.AVX512.Setup.exe
   ```

3. **VirusTotal.** Each VirusTotal link uses the file's SHA256, so it opens the report for exactly that file. It should show no detections. Some engines report "Timeout" or "Unable to process file type" on large installers and .7z archives; those are not detections. If an engine does flag a file, please open an issue before running it.

4. **Release attestation (153.8.0 and later).** Immutable releases carry a signed attestation. With the [GitHub CLI](https://cli.github.com/) installed:

   ```powershell
   gh release verify <tag>
   gh release verify-asset <tag> <asset-file>
   ```

5. **Signed tags.** Release tags from 153.0 on are signed, and GitHub shows them as Verified.

If any check doesn't match, don't run the file. Open an issue, or use the private reporting link at the bottom of this page.

## What protects a release

### Release integrity

- **Immutable releases are enabled.** Once a release is published, its files and tag can't be changed or moved. Releases are drafted first, all files are attached, and only then published.
- **Two independent hashes:** SHA512 in the release notes, plus the SHA256 digest GitHub generates for each file.
- **VirusTotal:** every file is scanned and linked from the release notes.
- **Manual approval:** a release is always created as a draft and goes public only after I approve it. After publishing, the automation checks that the release is public and attached to the right tag.

### Source provenance

- **Signed commits.** My commits to this repository have been SSH-signed since September 2026. Commits made in GitHub's web editor are signed by GitHub. Both show as Verified.
- **Signed tags.** See check 5 above.
- **Vigilant mode is on.** Any commit attributed to me that I didn't sign shows as Unverified, so a commit faked under my name stands out.
- **Protected tags and branch.** Repository rules stop any release tag from being moved or deleted, and stop `main` from being deleted or force-pushed (rewriting history).
- **Patch stack.** Each release tag points at the commit holding the patches (`Patches/`) used for that build, so every change on top of Mozilla's source can be inspected.
- **Open automation.** The scripts that build, hash, scan, and publish releases are in `Automation/`, minus the file holding their credentials.

### Build machine

- Releases are built and packaged on one local Windows PC. Nothing is built on GitHub's servers.
- All drives use full-disk encryption (BitLocker), with TPM and Secure Boot on.
- Microsoft Defender real-time and tamper protection are on, and the build folders are not excluded from scanning.
- The release signing key is readable only by my account and administrators. The GitHub CLI token is kept in Windows Credential Manager, not in a file.

### Account and repository

- Two-factor authentication is on for the maintainer account (authenticator app and passkey; no SMS).
- Secret scanning and push protection are on, so credentials can't be pushed by accident.
- Private vulnerability reporting is on.
- GitHub Actions is turned off for this repository, since nothing here runs on GitHub's servers.

### Built-in browser features

- The Firefox updater, maintenance service, default-browser agent, and crash reporter are compiled out.
- **Release check:** once a day, ducksteps asks `api.github.com` for the newest published version number. It is one anonymous request: no cookies, no referrer, and no account. Like any web request, it shows GitHub your IP address and browser version; GitHub doesn't pass any of that on to me. If a newer version exists, a bar appears at the top of the window and the About dialog shows a Download link to that release's page; nothing is downloaded or installed automatically. To turn it off, set `ducksteps.releasecheck.enabled` to `false` in `about:config`.

## Known limitations

- **The installers aren't code-signed (no Authenticode certificate).** Windows SmartScreen and some antivirus heuristics may warn about new, unsigned files. The checks above prove a file is the one I published, not that Windows will trust it.
- **Builds aren't reproducible**, and there has been no independent security audit.
- **Some older commits are unsigned.** 26 commits from before September 2026 predate signing, and GitHub marks them Unverified. I didn't rewrite history to sign them, because that would move every tag and break existing clones.
- **ducksteps follows Firefox ESR.** Security fixes come from Mozilla; each release's notes link the advisory it addresses.
- **One maintainer.** Reports are handled on a best-effort basis, with no guaranteed response time.

## Reporting a vulnerability

Please report privately: open the repository's **Security** tab and choose **Report a vulnerability** ([direct link](https://github.com/SyntaxError-PEBKAC/ducksteps/security/advisories/new)). Please don't open a public issue for something exploitable. If the problem is in Firefox itself and not in ducksteps' changes, report it to Mozilla too.
