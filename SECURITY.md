# Security Policy

**English** · [Português (BR)](SECURITY.pt-BR.md)

## Reporting a vulnerability

Report it **privately** through GitHub: open a draft advisory at
[Security → Report a vulnerability](https://github.com/ffapd1989/voice-note-transcriber/security/advisories/new).
That keeps the report private until a fix ships.

Please do not open a public issue for a security problem.

Include, if you can: the version, what an attacker gains, and the steps to reproduce.

This is a single-maintainer hobby project with no SLA. Expect an acknowledgement within a few
days. If two weeks pass with no reply, consider yourself free to disclose publicly.

## Supported versions

Only the latest release. There are no backports — fixes ship in the next version. Releases are
listed in [CHANGELOG.md](CHANGELOG.md).

## How your API key is handled

- Stored in the **Windows Credential Manager** under the target `TranscritorDeAudio/OpenAI`,
  encrypted by DPAPI under your Windows account. Not readable by another user, nor on another
  machine.
- **Never written to `config.json`.** A plaintext key left behind by an older version is
  stripped from the file and migrated into the vault on first load.
- "Forget key" in Settings deletes it from the vault.
- Sent only in the `Authorization` header of requests to the endpoint you configured.
- The app warns when that endpoint is plain `http://` outside localhost, since the key would
  otherwise travel unencrypted.

**The vault protects the key at rest, not from you.** Any process running as your Windows user
can read your Credential Manager — that is how DPAPI works. If your Windows account is
compromised, the key is compromised.

## Build integrity

- `ffmpeg.exe` is downloaded at build time from BtbN's LGPL builds and checked against a
  **pinned SHA-256**. If the upstream artifact changes, the build stops instead of silently
  accepting different bytes. See [build.ps1](build.ps1).
- UPX compression is deliberately disabled — it is a classic antivirus false-positive trigger.
- Dependencies are pinned to exact versions in [requirements.txt](requirements.txt).

## Known limitation: releases are not signed

The published executable carries no code signature. On first run Windows SmartScreen will warn
about an "unknown publisher", and you have to click **More info → Run anyway**.

Code signing certificates cost money every year and, since June 2023, require a hardware token
or a cloud HSM. For a free tool given away to friends, that is not currently justified.

**What this means for you:** that warning is expected, and clicking past it is not evidence
that the file is safe. If you care, build it yourself from source with `build.ps1` — the build
is reproducible from the pinned dependencies.

## Out of scope

- The unsigned binary and its SmartScreen warning, described above.
- Anything that requires an attacker to already be running code as your Windows user.
- The behaviour of OpenAI, or of any other endpoint you configure. See [PRIVACY.md](PRIVACY.md).
- Antivirus false positives on the PyInstaller bundle — report those to the antivirus vendor.
- The cost of API calls made with your own key.
