# Wordle Tracker Bot

A WhatsApp bot that automatically tracks Wordle scores from a group chat and posts daily and monthly leaderboards.

## How It Works

When a member of the WhatsApp group shares their Wordle result, the bot detects it, records the score in Firebase, and immediately replies with an updated leaderboard. Members can also request the monthly leaderboard at any time.

## Prerequisites

- Node.js v16+
- Python 3.10+
- A Firebase project with Firestore enabled
- A WhatsApp account to run the bot from
<<<<<<< HEAD
- pm2 (for background execution): `sudo npm install -g pm2`
=======
>>>>>>> 7340cad9f0d35009966ce3870363bc2ac01ca41e

## Setup

### 1. Clone and install Node dependencies

```bash
npm install
```

### 2. Set up Python environment

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Firebase

1. Go to the [Firebase Console](https://console.firebase.google.com/)
2. Open your project → Project Settings → Service Accounts
3. Click **Generate new private key** and download the JSON file
4. Rename it to `firebase-key.json` and place it in the project root
5. Ensure Firestore is enabled in your Firebase project (Firestore Database → Create database)

### 4. Set the WhatsApp group name

In `bot.js`, set `GROUP_NAME` to match the exact name of your WhatsApp group:

```js
const GROUP_NAME = "Wordle Group";
```

## Running the Bot

<<<<<<< HEAD
### Option 1 — Foreground (terminal stays busy)

=======
>>>>>>> 7340cad9f0d35009966ce3870363bc2ac01ca41e
```bash
npm start
```

<<<<<<< HEAD
### Option 2 — Background with pm2 (recommended)

pm2 is a process manager that runs the bot in the background, restarts it automatically if it crashes, and keeps logs accessible at any time. Install it once globally:

```bash
sudo npm install -g pm2
```

Then use these commands to manage the bot:

```bash
pm2 start bot.js --name wordle-bot   # start in background
pm2 stop wordle-bot                  # stop the bot
pm2 restart wordle-bot               # restart the bot
pm2 status                           # see if it's running
pm2 logs wordle-bot                  # view live logs
pm2 logs wordle-bot --lines 50       # view last 50 log lines
```

To make the bot start automatically when the machine boots:

```bash
pm2 startup     # generates a command — run the output it gives you
pm2 save        # saves the current process list
```

> pm2 is a system tool installed globally — it does not appear in `package.json` and will not show in `git status`.

=======
>>>>>>> 7340cad9f0d35009966ce3870363bc2ac01ca41e
On first run, a `whatsapp-qr.png` file is generated in the project root. Scan it with WhatsApp:

**WhatsApp → Settings → Linked Devices → Link a Device**

Once scanned, the terminal will print `WhatsApp Bot Ready!` and the QR image is automatically deleted. Your session is saved in `.wwebjs_auth/`, so subsequent runs will connect without a QR scan.

## Usage

### Submitting a Wordle score

Simply share your Wordle result in the group as normal. WhatsApp copies results in the format:

```
Wordle 1,738 4/6

⬛⬛🟨🟨⬛
⬛🟨⬛⬛🟨
🟩⬛🟨🟩⬛
🟩🟩🟩🟩🟩
```

The bot will reply with the daily leaderboard and your current monthly standing:

```
🎯 Wordle 1738 Leaderboard
1. Alice — 3/6
2. Bob — 4/6
3. Carol — X/6

 🏆 Monthly Leaderboard (March 2026)
1. Alice — 42 pts
2. Bob — 38 pts
3. Carol — 21 pts
```

### Requesting the monthly leaderboard

Send this message in the group:

```
Wordle Leaderboard March 2026
```

The bot will reply with the full monthly standings for that month.

## Scoring

Monthly points are calculated as `max_tries - score + 1` per puzzle. A score of 1/6 earns the most points (6), and a failed attempt (X/6) earns 0. Points accumulate across all puzzles played in the month.

| Score | Points (out of 6) |
|-------|-------------------|
| 1/6   | 6 pts             |
| 2/6   | 5 pts             |
| 3/6   | 4 pts             |
| 4/6   | 3 pts             |
| 5/6   | 2 pts             |
| 6/6   | 1 pt              |
| X/6   | 0 pts             |

## Notes

- Each player can only submit one score per puzzle — duplicates are rejected with a reminder of the original score
- The bot only listens to the group specified in `GROUP_NAME` and ignores all other chats
- `firebase-key.json` contains sensitive credentials — do not commit it to version control
