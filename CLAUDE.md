# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A WhatsApp bot that tracks Wordle scores for a group chat and maintains leaderboards via Firebase Firestore.

## Running the Bot

```bash
<<<<<<< HEAD
npm start                                    # foreground
pm2 start bot.js --name wordle-bot           # background (recommended)
```

The first run generates a `whatsapp-qr.png` QR code to scan with WhatsApp. Once scanned, the image is deleted automatically. Authentication is persisted via `LocalAuth` (stored in `.wwebjs_auth/`).

## Python Script

Invoked by `bot.js` as a subprocess — not run directly in normal operation.
=======
npm start          # starts bot.js via node
node bot.js        # equivalent
```

The first run will generate a `whatsapp-qr.png` QR code to scan with WhatsApp to authenticate. Once scanned, the image is deleted automatically. Authentication is persisted via `LocalAuth` (stored in `.wwebjs_auth/`).

## Python Script

The Python component is invoked by `bot.js` as a subprocess — not run directly in normal operation.
>>>>>>> 7340cad9f0d35009966ce3870363bc2ac01ca41e

```bash
# Manual test run (message must be base64-encoded)
python3 wordle_firebase.py "<sender_name>" "<base64_encoded_message>"
<<<<<<< HEAD

# Run tests
source venv/bin/activate && python -m unittest test_wordle -v
```

Dependencies: `pip install -r requirements.txt` (use a venv on Debian/Ubuntu)
=======
```

Dependencies: install via `pip install -r requirements.txt` (use a venv on Debian/Ubuntu)
>>>>>>> 7340cad9f0d35009966ce3870363bc2ac01ca41e

Requires `firebase-key.json` in the project root (Firebase service account credentials).

## Architecture

**Data flow:**
1. `bot.js` listens for WhatsApp messages in a group named `"Wordle Group"`
<<<<<<< HEAD
2. On a message starting with `"Wordle"`, it base64-encodes the message and spawns `wordle_firebase.py` as a subprocess
3. The Python script parses, writes to Firestore, and prints the response between `---Message Start---` / `---Message End---` markers
4. `bot.js` extracts that output and sends it back to the group as a WhatsApp code block
5. `bot.js` also runs a scheduled job every Sunday at 23:59 to automatically send the weekly leaderboard

**Supported commands:**
| Command | Description |
|---|---|
| `Wordle <puzzle> <score>/<max>` | Submit a score — saves to Firestore, returns daily + monthly leaderboard |
| `Wordle Leaderboard <Month> <Year>` | Monthly leaderboard |
| `Wordle Leaderboard This Week` | Current week's leaderboard (Mon–Sun) |
| `Wordle Stats <name> <Month> <Year>` | Personal stats for a player (names with spaces supported) |
| `Wordle vs <p1> vs <p2> <Month> <Year> [common]` | Head-to-head comparison; `common` restricts to shared puzzles only |

**Python class structure:**
- `WordleParser` — static methods only; parses messages and resolves puzzle numbers to dates via the NYT API
- `WordleTracker` — owns `self.db`; all Firestore operations (save, leaderboard, stats, head-to-head)

**Firestore collection:** `wordle_data`, documents keyed as `{puzzle}_{player}`. Fields: `puzzle`, `player`, `score`, `max_tries`, `date`, `month`, `year`.

**Scoring:** `max_tries - score + 1` per puzzle (higher = better). Failed attempts (X) score 0 points.
=======
2. On a message starting with `"Wordle"`, it base64-encodes the message body and spawns `wordle_firebase.py` as a subprocess, passing sender name and encoded message as args
3. The Python script parses the message, writes to Firestore, and prints the leaderboard between `---Message Start---` / `---Message End---` markers
4. `bot.js` extracts that delimited output and sends it back to the group chat as a WhatsApp code block

**Two message types handled by the Python script:**
- `Wordle <puzzle_number> <score>/<max>` — saves score and returns daily + monthly leaderboard
- `Wordle Leaderboard <Month> <Year>` — returns monthly leaderboard only

**Python class structure:**
- `WordleParser` — static methods only; handles message parsing and NYT API lookups to resolve puzzle number to date
- `WordleTracker` — owns `self.db`; handles all Firestore operations (duplicate check, save, leaderboard, monthly totals)

**Firestore collection:** `wordle_data`, documents keyed as `{puzzle}_{player}`. Each document stores: `puzzle`, `player`, `score`, `max_tries`, `date`, `month`, `year`.

**Puzzle date lookup:** Calls the NYT Wordle API (`nytimes.com/svc/wordle/v2/{date}.json`) to resolve a puzzle number to its calendar date via binary search.

**Scoring (monthly points):** `max_tries - score + 1` per puzzle (higher = better).
>>>>>>> 7340cad9f0d35009966ce3870363bc2ac01ca41e
