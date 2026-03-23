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

        return leaderboard_text + "\n\n" + monthly_text


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
                output = tracker.save_and_report(parsed)

            print("\n---Message Start---\n", output, "\n---Message End---")

        case "option_2":
            month, year = parsed.split()
            output = tracker.monthly_totals(month, year)

            if not output:
                output = f"No entries found for {month} {year}."

            print("\n---Message Start---\n", output, "\n---Message End---")

        case _:
            logging.info("No valid Wordle data found in the message.")

if __name__ == "__main__":
    main()
