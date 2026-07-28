# Changelog

All notable changes to this project are documented here.
This project follows [Semantic Versioning](https://semver.org/).

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
