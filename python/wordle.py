import re
import sqlite3
import datetime
import sys
import base64
import requests

DB_FILE = "wordle.db"

# --- Connect to SQLite ---
conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10)

# --- Setup Database ---
with conn:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        puzzle INTEGER,
        player TEXT,
        score INTEGER,
        max_tries INTEGER,
        date TEXT,
        month TEXT
    )
    """)

print("Database initialized.")

def get_wordle_by_id(puzzle, start_date=None):
    # If no date is given, start from today
    if start_date is None:
        date = datetime.date.today()
    else:
        date = datetime.date.fromisoformat(start_date)

    while True:
        url = f"https://www.nytimes.com/svc/wordle/v2/{date:%Y-%m-%d}.json"
        response = requests.get(url).json()
        current_puzzle = response["days_since_launch"]

        # Debug print (optional)
        print(f"Checking {date} -> ID {current_puzzle}")

        if current_puzzle == puzzle:
            return date
        elif current_puzzle > puzzle:
            date -= datetime.timedelta(days=1)
        else:
            date += datetime.timedelta(days=1)

# --- Parse Wordle ---
def parse_wordle(player, message):
    header_match = re.match(r"Wordle ([\d,]+) ([X\d])/(\d+)", message)
    print(f"Header match: {header_match}")
    
    if not header_match:
        return None

    puzzle = int(header_match.group(1).replace(',', ''))
    score = header_match.group(2)
    max_tries = int(header_match.group(3))

    score_val = max_tries + 1 if score == "X" else int(score)

    puzzle_date = get_wordle_by_id(puzzle)
    puzzle_date_reformatted = puzzle_date.strftime("%Y-%m-%d")
    month_key = puzzle_date.strftime("%B %Y")

    print(f"Parsed: {puzzle}, {player}, {score_val}, {max_tries}, {puzzle_date_reformatted}, {month_key}")
    return (puzzle, player, score_val, max_tries, puzzle_date_reformatted, month_key)

def duplicate_check(parsed):
    puzzle, player, score_val, max_tries, date, month = parsed
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM results WHERE puzzle=? AND player=?", (puzzle, player))
    count = c.fetchone()[0]

    if count > 0:
        c.execute("SELECT score FROM results WHERE puzzle=? AND player=?", (puzzle, player))
        existing_score = c.fetchone()[0]
        fail_message = f" (or at least tried to). " if existing_score > max_tries else ". "

        message = f"{player}! You've solved Wordle {puzzle} already" + fail_message + \
                  f"The score you got was {existing_score if existing_score <= max_tries else 'X'}/{max_tries}."
        return True, message
    
    return False, ""

# --- Save & generate leaderboard ---
def save_and_report(parsed):
    puzzle, player, score_val, max_tries, date, month = parsed

    with conn:
        conn.execute("""
        INSERT INTO results (puzzle, player, score, max_tries, date, month)
        VALUES (?, ?, ?, ?, ?, ?)
        """, parsed)

    # Return leaderboard text for WhatsApp, but keep all debug prints
    leaderboard_text = leaderboard(puzzle)
    monthly_text = monthly_totals(month)
    
    return leaderboard_text + "\n\n" + monthly_text

# --- Daily leaderboard ---
def leaderboard(puzzle_number):
    c = conn.cursor()
    c.execute("SELECT player, score, max_tries FROM results WHERE puzzle=? ORDER BY score ASC", (puzzle_number,))
    rows = c.fetchall()

    board = [f"🎯 Wordle {puzzle_number} Leaderboard"]
    index = 1

    for player, score, max_tries in rows:
        if score > max_tries:
            board.append(f"{index}. {player} — X/{max_tries}")
        else:
            board.append(f"{index}. {player} — {score}/{max_tries}")
        
        index += 1

    print(f"Generated leaderboard for Wordle {puzzle_number}")
    return "\n".join(board)

# --- Monthly totals ---
def monthly_totals(month):
    c = conn.cursor()
    c.execute("SELECT DISTINCT puzzle FROM results WHERE month=?", (month,))
    puzzles = [row[0] for row in c.fetchall()]

    scores = {}
    for puzzle in puzzles:
        c.execute("SELECT player, score, max_tries FROM results WHERE puzzle=? ORDER BY score ASC", (puzzle,))
        rows = c.fetchall()
        
        for player, score, max_tries in rows:
            points = max_tries - score + 1
            scores[player] = scores.get(player, 0) + points

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    board = [f"🏆 Monthly Leaderboard ({month})"]
    for i, (player, pts) in enumerate(sorted_scores, start=1):
        board.append(f"{i}. {player} — {pts} pts")

    print(f"Generated monthly totals for {month}")
    return "\n".join(board)

# --- Command-line integration ---
if __name__ == "__main__":
    print("Wordle parser started.")
    print(f"Arguments: {sys.argv}. Length: {len(sys.argv)}")

    if len(sys.argv) == 3:
        sender = sys.argv[1]
        message = base64.b64decode(sys.argv[2]).decode('utf-8')
        print(f"Decoded message: {message}")
        parsed = parse_wordle(sender, message)
        print(f"Parsed message: {parsed}")
        if parsed:
            duplicate_wordle, output = duplicate_check(parsed)
            if not duplicate_wordle:
                output = save_and_report(parsed)

            # Print leaderboard last, so Node.js can capture it
            print("\n---Message Start---")
            print(output)
            print("---Message End---")
    else:
        print("Usage: python wordle.py <sender> <message>")
