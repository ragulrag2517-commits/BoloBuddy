# BoloBuddy

**Speak • Learn • Play • Grow**

BoloBuddy is a local-first Streamlit learning prototype for foundational literacy and numeracy. It includes a child-friendly word garden, picture explorer, quiz, Hindi story, exact vocabulary lookup, worksheet PDFs, teacher-managed vocabulary, a local review queue, learning stars, progress, and a saved offline box.

## Run locally

1. Use Python 3.10 or later.
2. In the project folder, create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and start Streamlit:

   ```powershell
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```

The app opens in your browser. The SQLite database is created at `data/bolobuddy.sqlite3` on first run. Stop the local server with Ctrl+C.

## Language integrity

Hindi starter words are included. Santhali, Ho and Mundari are selectable, but no unverified translations are prefilled. The app only presents translations that have been approved in its local review flow. A reviewer records their name, a community/source reference, and confirms native-speaker review before an entry is approved. This is a local prototype; it does not verify identities or synchronize community contributions.

Approved words are persisted in SQLite and written back to `language_data.json`. Back up both files to preserve the local word library and learner progress.

## What works—and what does not

- Vocabulary categories, picture reveal, exact approved-word lookup, and browser speech playback.
- Quiz and story feedback with SQLite-persisted activity and stars.
- A ReportLab worksheet PDF with word matching and counting practice.
- Teacher vocabulary entry, pending community contributions, local approval/rejection, and offline saved words.
- Browser speech synthesis depends on an installed voice. Exact lookup is not an AI translator.
- Microphone recording can be played back in the current session, but is not transcribed or translated.
- Saved offline items are available from the local database while this local app runs without internet. This is not a browser-installable offline app and has no cross-device sync.
- The UI uses local system fonts and does not require an internet connection. Hindi PDF text uses an installed Devanagari font when available; without one, script answer choices are left blank rather than rendered as missing glyphs.
- Worksheet practice is inspired by foundational learning goals and is not an official NIPUN Bharat assessment.

## Project layout

```text
BoloBuddy/
├── app.py
├── database.py
├── language_data.json
├── translator.py
├── worksheet.py
├── requirements.txt
├── tests/
└── assets/
    └── styles/
        └── custom.css
```

## Run tests

```powershell
python -m pytest
```
