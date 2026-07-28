TRANSCRITOR DE AUDIO DE ZAP - v2.1.0
(a.k.a. WhatsApp voice note transcriber)
=====================================

WHAT IS THIS
------------
A Windows application that transcribes audio files (MP3, M4A,
WhatsApp voice notes in OGG/OPUS, WAV, and others) using OpenAI's
Whisper API,
with an optional cleanup/formatting pass by GPT. Just drag the
file onto the window, wait, and copy or save the resulting text.
The theme (light/dark) follows Windows and can be pinned with the
button at the top of the app.

YOU NEED YOUR OWN OPENAI API KEY
---------------------------------
The app does not ship with a built-in key - each person uses their
own, and the transcription cost is billed to whoever's OpenAI
account is used (a few cents per audio file).

Important: the key is never written to a plain text file. It is
stored in the Windows Credential Manager, encrypted with your
account - it only opens under your user, on this machine. You
enter the key once; to remove it later, use the "Forget key"
button in the app's Settings.

How to get your key:
1. Go to https://platform.openai.com and create an account (or
   sign in to yours).
2. In the menu, go to "API keys" and click "Create new secret
   key".
3. Copy the key (it starts with "sk-...") and keep it somewhere
   safe - it is only shown once.
4. You need credit on the account (the "Billing" tab); a few
   dollars go a long way.
5. Paste the key into the app the first time you open it - it is
   stored securely from then on.

WINDOWS WARNING (SMARTSCREEN)
------------------------------
On first launch, Windows may show a blue screen saying the app
"was prevented from starting" or is from an "unknown publisher".
This is normal for programs without a digital signature (which is
expensive and mostly used by companies). To run it anyway:

1. Click "More info".
2. Click "Run anyway".

This warning only appears the first time.

REQUIREMENTS
-------------
- Windows 10 or 11, 64-bit.
- Internet connection (transcription happens on OpenAI's servers).
- OpenAI API key (see above).

Nothing needs to be installed: "Transcritor de Audio de Zap.exe"
already contains everything it needs.
Questions or problems: contact whoever sent you this file.
