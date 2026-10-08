# My PC AI Agent

Native Android AI-agent app.

## Features
- Bengali/English chat
- Bengali voice input
- Gemini cloud chat when the PC is off
- Optional PC Agent URL setting for future PC-on control
- API key is entered by the user and stored only in Android local preferences; it is not committed to GitHub or hard-coded into the APK
- GitHub Actions builds the debug APK automatically

## Cloud AI
The app currently uses the Gemini API model `gemini-2.5-flash-lite`. A Gemini API key is required for cloud chat. Free-tier availability and limits are controlled by Google and can change.

Never commit an API key to this repository.
