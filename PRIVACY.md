# Privacy Policy

**English** · [Português (BR)](PRIVACY.pt-BR.md)

## Summary

Transcritor de Áudio de Zap runs entirely on your computer. It has no backend. The author
operates no servers, collects nothing, and receives nothing from your use of the app — no
telemetry, no analytics, no crash reports, no update checks, no account, no registration.

The app does send your audio to a speech-to-text API, because that is the whole point of it.
You choose the provider and you supply the key. That is the only network traffic it generates.

## What leaves your computer

Only requests to the API endpoint set in Settings. By default that is `https://api.openai.com/v1`.

| When | Request | What is sent |
|---|---|---|
| You transcribe a file | `POST /audio/transcriptions` | The audio file contents and its filename, the selected model, and a language code if you picked one instead of `auto` |
| GPT cleanup or Rewrite runs | `POST /chat/completions` | The transcribed **text** and the prompt. The audio is not sent again |
| You click "Test key" | `GET /models` | Nothing beyond the key itself |

Your API key travels in the `Authorization` header of those requests. Nothing else is
transmitted — no device identifiers, no usage counters, no file inventory.

If you point the **Endpoint** field at a different OpenAI-compatible service (LM Studio,
Ollama, Groq, Azure OpenAI, your own server), those same requests go there instead. The app
warns you when an endpoint uses plain `http://` outside localhost, because your key would
travel in the clear.

## What stays on your computer

| Item | Location | Notes |
|---|---|---|
| Preferences | `%APPDATA%\TranscricaoApp\config.json` | Models, audio language, theme, interface language, custom prompt, endpoint. **Never the API key** |
| API key | Windows Credential Manager, target `TranscritorDeAudio/OpenAI` | Encrypted by DPAPI under your Windows account — readable only by you, only on that machine |
| Your audio files | Wherever you keep them | The app reads them in place. It never copies, moves or uploads them anywhere other than the endpoint above |
| Temporary files | `%TEMP%` | Created only to convert Opus for playback, or to compress a file over 25 MB. Deleted when the app closes normally |
| Transcriptions | Memory only | They live in the window until you close it, and reach the disk only when you click "Save .txt" |

The activity log shown in the app window is held in memory and is never written to a file.

If an old `config.json` from a previous version still holds a plaintext `api_key`, the app
strips it from the file on load and migrates it into Credential Manager.

Temporary file cleanup runs when the app exits normally. If it is force-killed or crashes, a
temporary file may survive in `%TEMP%` until Windows clears it.

## The third party you chose

Once your audio reaches OpenAI — or whichever endpoint you configured — what happens to it is
governed by that provider's terms, not by this app. The author has no visibility into it and
no agreement with them on your behalf.

For OpenAI, see their [API data usage policies](https://openai.com/policies/api-data-usage-policies)
and [Privacy Policy](https://openai.com/policies/privacy-policy).

If you would rather no audio leave your network at all, point the Endpoint field at a local
server such as LM Studio or Ollama.

## What the author receives

Nothing.

The only other network activity the app can cause is opening a link in your browser when you
click one — the OpenAI signup, API keys and billing pages, or the project's GitHub page.

## Changes

This document describes the app as currently released. Changes ship with a version and are
recorded in [CHANGELOG.md](CHANGELOG.md).

## Questions

Open an issue at [github.com/ffapd1989/voice-note-transcriber](https://github.com/ffapd1989/voice-note-transcriber/issues).
