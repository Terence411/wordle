import re
import datetime
import sys
import base64
import requests
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")

VALID_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


class WordleParser:
    """Handles parsing of incoming WhatsApp messages. No database interaction."""

    @staticmethod
    def get_wordle_by_id(puzzle, start_date=None):
        if start_date is None:
            date = datetime.date.today()
        else:
            date = datetime.date.fromisoformat(start_date)

        while True:
            url = f"https://www.nytimes.com/svc/wordle/v2/{date:%Y-%m-%d}.json"
            try:
                response = requests.get(url).json()
            except Exception as e:
                raise RuntimeError(f"Failed fetching Wordle data: {e}")

            if "days_since_launch" not in response:
                raise RuntimeError(f"No Wordle data available for {date}")

            current_puzzle = response["days_since_launch"]
            logging.info(f"Checking {date} -> ID {current_puzzle}")

            if current_puzzle == puzzle:
                return date
            elif current_puzzle > puzzle:
                date -= datetime.timedelta(days=1)
            else:
                date += datetime.timedelta(days=1)

    @staticmethod
    def parse(player, message):
        # Case #1: "Wordle <puzzle> <score>/<max_tries>"
        match = re.match(r"Wordle ([\d,]+) ([X\d])/(\d+)\s*(?:\n|$)", message)
        logging.info(f"Case #1 match: {match}")

        if match:
            puzzle = int(match.group(1).replace(',', ''))
            score = match.group(2)
            max_tries = int(match.group(3))

            score_val = max_tries + 1 if score == "X" else int(score)

            puzzle_date = WordleParser.get_wordle_by_id(puzzle)
            puzzle_date_reformatted = puzzle_date.strftime("%Y-%m-%d")
            month = puzzle_date.strftime("%B")
            year = puzzle_date.strftime("%Y")

            print(f"Parsed: {puzzle}, {player}, {score_val}, {max_tries}, {puzzle_date_reformatted}, {month}, {year}")
            return (puzzle, player, score_val, max_tries, puzzle_date_reformatted, month, year), "option_1"

        # Case #3: "Wordle Stats <name> <month> <year>"
        match = re.match(r"Wordle Stats (.+?)\s+(\w+)\s+(\d{4})\s*$", message, re.IGNORECASE)
        logging.info(f"Case #3 match: {match}")

        if match:
            player_name = match.group(1).strip()
            month_name = match.group(2).capitalize()
            year_str = match.group(3)

            if month_name not in VALID_MONTHS:
                logging.info(f"Invalid month detected: {month_name}")
                return None, None

            logging.info(f"Parsed stats request for {player_name} in {month_name} {year_str}")
            return (player_name, month_name, year_str), "option_3"

        # Case #4: "Wordle Leaderboard Current" — must be before Case #2
        match = re.match(r"Wordle Leaderboard Current\s*$", message, re.IGNORECASE)
        logging.info(f"Case #4 match: {match}")

        if match:
            logging.info("Parsed current month leaderboard request")
            return None, "option_4"

        # Case #2: "Wordle Leaderboard <Month> <Year>"
        match = re.match(r"Wordle Leaderboard (\w+) (\d{4})", message, re.IGNORECASE)
        logging.info(f"Case #2 match: {match}")

        if match:
            month_name = match.group(1).capitalize()
            current_year = match.group(2)

            if month_name not in VALID_MONTHS:
                logging.info(f"Invalid month detected: {month_name}")
                return None, None

            month_year_key = f"{month_name} {current_year}"
            logging.info(f"Parsed leaderboard request for {month_year_key}")
            return month_year_key, "option_2"

        # Case #5: "Wordle vs <player1> vs <player2> [vs ...] <month> <year> [common]"
        match = re.match(r"Wordle vs (.+?)\s+(\w+)\s+(\d{4})(\s+common)?\s*$", message, re.IGNORECASE)
        logging.info(f"Case #5 match: {match}")

        if match:
            players = [p.strip() for p in re.split(r'\s+vs\s+', match.group(1), flags=re.IGNORECASE)]
            month_name = match.group(2).capitalize()
            year_str = match.group(3)
            common_mode = match.group(4) is not None

            if month_name not in VALID_MONTHS:
                logging.info(f"Invalid month detected: {month_name}")
                return None, None

            if len(players) < 2:
                logging.info("Head-to-head requires at least 2 players")
                return None, None

            logging.info(f"Parsed head-to-head: {players}, {month_name} {year_str}, common={common_mode}")
            return (players, month_name, year_str, common_mode), "option_5"

        return None, None


class WordleTracker:
    """Handles all Firebase interactions: saving scores, duplicate checking, and leaderboards."""

    def __init__(self):
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        logging.info("Connected to Firebase Firestore.")

    def duplicate_check(self, parsed):
        puzzle, player, score_val, max_tries, date, month, year = parsed

        results_ref = self.db.collection("wordle_data")
        query = results_ref.where(filter=FieldFilter("puzzle", "==", puzzle)).where(filter=FieldFilter("player", "==", player)).stream()
        docs = list(query)

        if docs:
            existing_score = docs[0].to_dict().get("score", None)
            fail_message = " (or at least tried to). " if existing_score and existing_score > max_tries else ". "

            message = (
                f"{player}! You've solved Wordle {puzzle} already" + fail_message +
                f"The score you got was {existing_score if existing_score and existing_score <= max_tries else 'X'}/{max_tries}."
            )

            logging.info(f"Duplicate entry detected for player {player} on puzzle {puzzle}.")
            return True, message

        return False, ""

    def leaderboard(self, puzzle_number):
        results = (
            self.db.collection("wordle_data")
            .where(filter=FieldFilter("puzzle", "==", puzzle_number))
            .stream()
        )

        rows = []
        for doc in results:
            data = doc.to_dict()
            rows.append((data["player"], data["score"], data["max_tries"]))

        rows.sort(key=lambda x: x[1])

        board = [f"🎯 Wordle {puzzle_number} Leaderboard"]
        for index, (player, score, max_tries) in enumerate(rows, start=1):
            if score > max_tries:
                board.append(f"{index}. {player} — X/{max_tries}")
            else:
                board.append(f"{index}. {player} — {score}/{max_tries}")

        logging.info(f"Generated leaderboard for Wordle {puzzle_number}")
        return "\n".join(board)

    def monthly_totals(self, month, year):
        results = (
            self.db.collection("wordle_data")
            .where(filter=FieldFilter("month", "==", month))
            .where(filter=FieldFilter("year", "==", year))
            .stream()
        )

        scores = {}
        for doc in results:
            data = doc.to_dict()
            points = data["max_tries"] - data["score"] + 1
            scores[data["player"]] = scores.get(data["player"], 0) + points

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        board = [f" 🏆 Monthly Leaderboard ({month} {year})"]
        for i, (player, pts) in enumerate(sorted_scores, start=1):
            board.append(f"{i}. {player} — {pts} pts")

        logging.info(f"Generated monthly totals for {month} {year}")
        return "\n".join(board)

    def save_and_report(self, parsed):
        puzzle, player, score_val, max_tries, date, month, year = parsed

        # Check if this is the first submission for this puzzle
        existing = list(
            self.db.collection("wordle_data")
            .where(filter=FieldFilter("puzzle", "==", puzzle))
            .stream()
        )
        is_first = len(existing) == 0

        doc_ref = self.db.collection("wordle_data").document(f"{puzzle}_{player}")
        doc_ref.set({
            "puzzle": puzzle,
            "player": player,
            "score": score_val,
            "max_tries": max_tries,
            "date": date,
            "month": month,
            "year": year
        })

        leaderboard_text = self.leaderboard(puzzle)
        monthly_text = self.monthly_totals(month, year)

        banner = ""
        if is_first:
            score_display = "X" if score_val > max_tries else str(score_val)
            banner = f"🥇 {player} is the first to submit today — sets the bar at {score_display}/{max_tries}!\n\n"

        return banner + leaderboard_text + "\n\n" + monthly_text

    def player_stats(self, player, month, year):
        results = list(
            self.db.collection("wordle_data")
            .where(filter=FieldFilter("player", "==", player))
            .where(filter=FieldFilter("month", "==", month))
            .where(filter=FieldFilter("year", "==", year))
            .stream()
        )

        if not results:
            return f"No entries found for {player} in {month} {year}."

        games_played = len(results)
        scores = [doc.to_dict()["score"] for doc in results]
        max_tries_vals = [doc.to_dict()["max_tries"] for doc in results]

        failures = sum(1 for s, m in zip(scores, max_tries_vals) if s > m)
        valid_scores = [s for s, m in zip(scores, max_tries_vals) if s <= m]

        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else "N/A"
        best_score = min(valid_scores) if valid_scores else "N/A"

        lines = [
            f"📊 Stats for {player} — {month} {year}",
            f"Games Played : {games_played}",
            f"Average Score: {avg_score}",
            f"Best Score   : {best_score}",
            f"Failures (X) : {failures}",
        ]

        logging.info(f"Generated stats for {player} in {month} {year}")
        return "\n".join(lines)

    def current_leaderboard(self):
        today = datetime.date.today()
        first_of_month = today.replace(day=1)

        first_str = first_of_month.strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        results = list(
            self.db.collection("wordle_data")
            .where(filter=FieldFilter("date", ">=", first_str))
            .where(filter=FieldFilter("date", "<=", today_str))
            .stream()
        )

        if not results:
            return f"No entries found for this month so far ({first_str} to {today_str})."

        scores = {}
        for doc in results:
            data = doc.to_dict()
            points = data["max_tries"] - data["score"] + 1
            scores[data["player"]] = scores.get(data["player"], 0) + points

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        month_name = today.strftime("%B")
        board = [f"📅 {month_name} Leaderboard ({first_str} to {today_str})"]
        for i, (player, pts) in enumerate(sorted_scores, start=1):
            board.append(f"{i}. {player} — {pts} pts")

        logging.info(f"Generated current month leaderboard for {first_str} to {today_str}")
        return "\n".join(board)

    def head_to_head(self, players, month, year, common_only):
        # Fetch each player's submissions for the month as {puzzle: {score, max_tries}}
        player_data = {}
        for player in players:
            results = list(
                self.db.collection("wordle_data")
                .where(filter=FieldFilter("player", "==", player))
                .where(filter=FieldFilter("month", "==", month))
                .where(filter=FieldFilter("year", "==", year))
                .stream()
            )
            player_data[player] = {
                doc.to_dict()["puzzle"]: {
                    "score": doc.to_dict()["score"],
                    "max_tries": doc.to_dict()["max_tries"]
                }
                for doc in results
            }

        # Shared puzzles = puzzles submitted by ALL players
        all_puzzle_sets = [set(d.keys()) for d in player_data.values()]
        shared_puzzles = set.intersection(*all_puzzle_sets) if all_puzzle_sets else set()

        # In common_only mode, restrict active set to shared puzzles
        if common_only:
            active_data = {
                player: {p: s for p, s in data.items() if p in shared_puzzles}
                for player, data in player_data.items()
            }
        else:
            active_data = player_data

        # Count wins on shared puzzles (lowest score wins; ties award no one)
        wins = {player: 0 for player in players}
        for puzzle in shared_puzzles:
            puzzle_scores = {
                player: player_data[player][puzzle]["score"]
                for player in players
                if puzzle in player_data[player]
            }
            if not puzzle_scores:
                continue
            min_score = min(puzzle_scores.values())
            winners = [p for p, s in puzzle_scores.items() if s == min_score]
            if len(winners) == 1:
                wins[winners[0]] += 1

        # Compute per-player stats from active set
        summaries = []
        for player in players:
            active = active_data[player]
            games = len(active)
            valid_scores = [v["score"] for v in active.values() if v["score"] <= v["max_tries"]]
            avg = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else "N/A"
            summaries.append((player, games, avg, wins[player]))

        summaries.sort(key=lambda x: (-x[3], x[2] if isinstance(x[2], float) else float('inf')))

        header = f"⚔️  Head-to-Head: {' vs '.join(players)} ({month} {year})"
        lines = [header]

        if common_only:
            lines.append(f"(Common puzzles only — {len(shared_puzzles)} shared)")

        for player, games, avg, w in summaries:
            lines.append(f"{player}: {games} games | avg {avg} | {w} wins")

        if not shared_puzzles:
            lines.append("(No shared puzzles found — wins not applicable)")

        logging.info(f"Generated head-to-head for {players} in {month} {year}")
        return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print("Usage: python wordle.py <sender> <message>")
        return

    sender = sys.argv[1]
    message = base64.b64decode(sys.argv[2]).decode('utf-8')
    logging.info(f"Decoded message: {message}")

    tracker = WordleTracker()
    parsed, options_list = WordleParser.parse(sender, message)
    logging.info(f"Parsed message: {parsed}")

    match options_list:
        case "option_1":
            duplicate_wordle, output = tracker.duplicate_check(parsed)
            if not duplicate_wordle:
                tracker.save_and_report(parsed)
                print("\n---Reaction---\n✅\n---End Reaction---")
            else:
                print("\n---Message Start---\n", output, "\n---Message End---")

        case "option_2":
            month, year = parsed.split()
            output = tracker.monthly_totals(month, year)

            if not output:
                output = f"No entries found for {month} {year}."

            print("\n---Message Start---\n", output, "\n---Message End---")

        case "option_3":
            player_name, month, year = parsed
            output = tracker.player_stats(player_name, month, year)

            print("\n---Message Start---\n", output, "\n---Message End---")

        case "option_4":
            output = tracker.current_leaderboard()

            print("\n---Message Start---\n", output, "\n---Message End---")

        case "option_5":
            players, month, year, common_mode = parsed
            output = tracker.head_to_head(players, month, year, common_mode)

            print("\n---Message Start---\n", output, "\n---Message End---")

        case _:
            logging.info("No valid Wordle data found in the message.")

if __name__ == "__main__":
    main()
