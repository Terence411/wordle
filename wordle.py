import re
import sqlite3
from datetime import datetime
import sys
import base64

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

    today = datetime.now()
    month_key = today.strftime("%Y-%m")
    
    print(f"Parsed: {puzzle}, {player}, {score_val}, {max_tries}, {today}, {month_key}")
    return (puzzle, player, score_val, max_tries, today.strftime("%Y-%m-%d"), month_key)

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

    board = [f"🏆 Wordle {puzzle_number} Leaderboard"]
    rank = 1
    for player, score, max_tries in rows:
        if score > max_tries:
            board.append(f"❌ {player} — X/{max_tries}")
        else:
            board.append(f"{rank}. {player} — {score}/{max_tries}")
            rank += 1

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
        rank = 1
        for player, score, max_tries in rows:
            if score > max_tries:
                points = 0
            elif rank == 1:
                points = 3; rank += 1
            elif rank == 2:
                points = 2; rank += 1
            elif rank == 3:
                points = 1; rank += 1
            else:
                points = 0
            scores[player] = scores.get(player, 0) + points

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    board = [f"📅 Monthly Leaderboard ({month})"]
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
            output = save_and_report(parsed)
            # Print leaderboard last, so Node.js can capture it
            print("\n---Leaderboard Start---")
            print(output)
            print("---Leaderboard End---")
    else:
        print("Usage: python wordle.py <sender> <message>")
