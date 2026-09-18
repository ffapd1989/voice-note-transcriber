# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [2.4.0] — 2026-09-18

### Added

- **Privacy and security policies.** `PRIVACY.md` and `SECURITY.md`, each with
  a Portuguese counterpart, documenting exactly what leaves the machine (only
  the three API calls it makes), what stays on it, and how to report a
  vulnerability privately.

### Changed

- **`gpt-transcribe` is the new default transcription model**, replacing
  `gpt-4o-mini-transcribe`. The `gpt-4o-*` models remain in the list for
  compatible endpoints that do not expose the newer one yet.
- **`gpt-5.6-luna` is the new default rewrite model**, replacing
  `gpt-4.1-nano`.
- **"GPT model" is now "Rewrite model"** in the interface, in all three
  languages.
- **Configs sitting on the previous defaults migrate on first launch**, the
  same way `whisper-1` and `gpt-4.1-mini` already did. A choice that differs
  from an old default is left untouched.
- **Cost figures corrected.** Transcription is US$ 0.0045 per minute with
  `gpt-transcribe`; rewriting a thousand words costs under half a cent with
  Luna, where the previous text said "a few cents".

## [2.3.0] — 2026-08-11

### Added

- **Automatic compaction for files over 25MB.** The Whisper API rejects
  anything bigger than that; instead of only failing at upload time, the app
  now asks — as soon as an oversized file is dropped — whether to compact it
  automatically (re-encodes to mono 16kHz Opus at a bitrate computed to fit
  the limit) before queuing it for transcription. Declining just skips that
  file; the rest of the batch still goes through.

### Changed

- **The executable is noticeably bigger.** Compaction is done with a bundled
  static FFmpeg binary (LGPL license, ffmpeg.org) — there's no way around its
  size, roughly 110MB, so first-launch antivirus scanning may take longer
  than previous releases.

## [2.2.1] — 2026-07-28

### Fixed

- **The packaged executable did not start at all.** Pillow is a direct dependency
  — the UI draws its chevron, "+" badge and GitHub icon with PIL — but it was
  missing from `requirements.txt`, reaching the build only as a transitive
  dependency of customtkinter, which stopped shipping it in 6.0.0. A clean build
  therefore produced an executable without PIL that raised `ModuleNotFoundError`
  while building the first dropdown. Because the app is packaged with
  `console=False`, this failed silently: double-clicking it did nothing at all.
  Pillow is now pinned explicitly.

### Changed

- **The executable is now named `transcrizap.exe`** (it was
  `Transcritor de Audio de Zap.exe`). Some corporate endpoint protection —
  Trend Micro Apex One Application Control, in the case that prompted this —
  keeps deny rules keyed to the *file name*: the very same bytes were denied
  execution under the old name and ran fine under any other, anywhere on disk.
  A short, unremarkable name avoids that class of collision. The product name
  shown in the title bar and in the file properties is unchanged.

## [2.2.0] — 2026-07-28

### Changed

- **Recommended models are now the defaults:** `gpt-4o-mini-transcribe` for
  transcription (more accurate and cheaper than `whisper-1`) and `gpt-4.1-nano`
  for the GPT cleanup pass. Existing configs still on the old defaults are
  migrated automatically; an explicit choice is never overwritten.
- `whisper-1` moved to the end of the model list and is documented as legacy,
  kept only for third-party endpoints that don't expose the newer models.
- The "Whisper model" label became "Transcription model" — the default model is
  no longer a Whisper one.

### Added

- **Built-in guide on how to get an OpenAI API key**, opened from the "How do I
  get a key?" link in Settings and whenever a transcription is attempted without
  a key. Numbered steps, buttons that open the right OpenAI pages, cost estimate
  and a note that the API is prepaid and separate from ChatGPT.
- Recommended model shown under each model selector.

## [2.1.0] — 2026-07-28

### Added

- **Multilingual interface** (Portuguese, English, Spanish, plus `auto` following
  Windows with English fallback), switchable from the footer with no restart —
  transcriptions already on screen are preserved.
- **Default cleanup prompt in 8 languages** (pt, en, es, fr, de, it, ja, zh). It
  follows the interface language; when the audio language is one the interface
  doesn't cover, that one wins. A custom prompt is never overwritten, and
  "Restore default" brings back the current language's version.
- **Test key** button — validates the API key with `GET {base}/models` and reports
  how many models are available.
- **Configurable endpoint** — any OpenAI v1-compatible API; leave empty for OpenAI.
  Warns if a non-local `http://` endpoint would send the key in clear text.
- **Audio language selector on the main screen**, synchronised with the one in
  Settings (both share the same state).
- **Visual identity**: amber-on-graphite palette, a unique waveform per file that
  pulses while transcribing and becomes the player's seek bar, three-layer
  typography, and a chat-bubble logo used as the window and executable icon.
- **Manual theme toggle** (auto / light / dark), persisted, on top of the
  automatic Windows theme detection — including the title bar.
- **Documentation in English and Portuguese**, MIT license, distribution README.

### Changed

- Cleanup prompt is no longer stored in `config.json` unless customised, so the
  default can follow the interface language.
- Audio language defaults to `auto` (Whisper detects it).
- Dropdowns replaced with a custom component: the chevron is rendered at 8× and
  downscaled with LANCZOS, fixing the jagged arrow of the stock widget.

### Security

- `tempfile.mktemp()` replaced with `mkstemp()` in the Opus→WAV conversion,
  removing the predictable-name race window.
- Repository history rebuilt from scratch before publication, dropping committed
  build artifacts and internal infrastructure notes.

## [2.0.0] — 2026-07-28

### Security

- **The API key is never written to a plain-text file.** It moved to the Windows
  Credential Manager (DPAPI, per-account). Existing `config.json` files are
  scrubbed on load and the key is migrated into the vault automatically.

### Added

- Automatic light/dark theme following Windows.
- Portable PyInstaller spec (no absolute paths), Windows version info, and
  `build.ps1 -Zip` producing a ready-to-share package.

### Fixed

- A second drag & drop replaced the queue instead of appending to it.

### Removed

- Colour emoji throughout the UI, which rendered poorly and without antialiasing.

## [1.0.0]

- Initial version, derived from an n8n transcription workflow.
