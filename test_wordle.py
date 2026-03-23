"""
Run all tests:
    source venv/bin/activate
    python -m unittest test_wordle -v

Run a single test:
    python -m unittest test_wordle.TestWordleParser.test_normal_score_submission
    python -m unittest test_wordle.TestWordleTracker.test_duplicate_check_detects_existing_entry
"""

import unittest
from unittest.mock import MagicMock, patch

from wordle_firebase import WordleParser, WordleTracker


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def make_nyt_response(puzzle_id):
    """Fake a successful NYT API response for a given puzzle ID."""
    mock = MagicMock()
    mock.json.return_value = {"days_since_launch": puzzle_id, "solution": "CRANE"}
    return mock


def make_nyt_empty_response():
    """Fake an NYT API response with no puzzle data (future/very old puzzle)."""
    mock = MagicMock()
    mock.json.return_value = {}
    return mock


def make_firestore_doc(player, score, max_tries, puzzle=1738, month="March", year="2026"):
    """Fake a Firestore document."""
    doc = MagicMock()
    doc.to_dict.return_value = {
        "puzzle": puzzle,
        "player": player,
        "score": score,
        "max_tries": max_tries,
        "date": "2026-03-23",
        "month": month,
        "year": year,
    }
    return doc


SAMPLE_GRID = "\n\n⬛⬛🟨🟨⬛\n⬛🟨⬛⬛🟨\n🟩⬛🟨🟩⬛\n🟩🟩🟩🟩🟩"
FAILED_GRID = "\n\n⬛⬛⬛⬛⬛\n⬛⬛⬛⬛⬛\n⬛⬛⬛⬛⬛\n⬛⬛⬛⬛⬛\n⬛⬛⬛⬛⬛\n⬛⬛⬛⬛⬛"


# ──────────────────────────────────────────────
#  WordleParser tests  (no Firebase needed)
# ──────────────────────────────────────────────

class TestWordleParser(unittest.TestCase):

    # 1. Normal score submission
    # Message: "Wordle 1,738 4/6\n\n⬛⬛🟨🟨⬛\n..."
    # Expected: parsed as option_1, score=4, player=Terence, puzzle=1738
    @patch("requests.get")
    def test_normal_score_submission(self, mock_get):
        mock_get.return_value = make_nyt_response(1738)
        message = "Wordle 1,738 4/6" + SAMPLE_GRID
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)

        self.assertEqual(option, "option_1")
        puzzle, player, score, max_tries, _, month, year = parsed
        self.assertEqual(puzzle, 1738)
        self.assertEqual(player, "Terence")
        self.assertEqual(score, 4)
        self.assertEqual(max_tries, 6)
        self.assertEqual(month, "March")
        self.assertEqual(year, "2026")

    # 4. X score (failed attempt — player did not solve the puzzle)
    # Message: "Wordle 1,738 X/6\n\n⬛⬛⬛⬛⬛\n..."
    # Expected: score stored as max_tries + 1 (i.e. 7 for /6)
    @patch("requests.get")
    def test_x_score_parsed_as_max_plus_one(self, mock_get):
        mock_get.return_value = make_nyt_response(1738)
        message = "Wordle 1,738 X/6" + FAILED_GRID
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)

        self.assertEqual(option, "option_1")
        _, _, score, max_tries, _, _, _ = parsed
        self.assertEqual(score, max_tries + 1)  # X stored as 7 for /6

    # 3. Monthly leaderboard request
    # Message: "Wordle Leaderboard March 2026"
    # Expected: parsed as option_2 with key "March 2026"
    def test_monthly_leaderboard_request(self):
        message = "Wordle Leaderboard March 2026"
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)
        self.assertEqual(option, "option_2")
        self.assertEqual(parsed, "March 2026")

    # Leaderboard request with lowercase — should still be accepted
    # Message: "wordle leaderboard march 2026"
    # Expected: parsed as option_2 with key "March 2026"
    def test_monthly_leaderboard_case_insensitive(self):
        message = "wordle leaderboard march 2026"
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)
        self.assertEqual(option, "option_2")
        self.assertEqual(parsed, "March 2026")

    # 5. Altered message — player added text after the score
    # Message: "Wordle 1,738 4/6 I did so well today!\n\n⬛⬛🟨🟨⬛\n..."
    # Expected: rejected, returns (None, None)
    @patch("requests.get")
    def test_altered_message_with_extra_text_is_ignored(self, mock_get):
        mock_get.return_value = make_nyt_response(1738)
        message = "Wordle 1,738 4/6 I did so well today!" + SAMPLE_GRID
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)

        self.assertIsNone(parsed)
        self.assertIsNone(option)

    # 6. Puzzle ID not found in NYT API (future or very old puzzle)
    # Message: "Wordle 99999 4/6\n\n⬛⬛🟨🟨⬛\n..."
    # Expected: RuntimeError raised during NYT API lookup
    @patch("requests.get")
    def test_invalid_puzzle_id_raises_error(self, mock_get):
        mock_get.return_value = make_nyt_empty_response()
        message = "Wordle 99999 4/6" + SAMPLE_GRID
        print(f"\n[Test message] {repr(message)}")

        with self.assertRaises(RuntimeError):
            WordleParser.parse("Terence", message)

    # Leaderboard request with a made-up month name
    # Message: "Wordle Leaderboard Octember 2026"
    # Expected: rejected, returns (None, None)
    def test_invalid_month_in_leaderboard_request(self):
        message = "Wordle Leaderboard Octember 2026"
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)
        self.assertIsNone(parsed)
        self.assertIsNone(option)

    # Completely unrelated message sent in the group
    # Message: "Hey everyone, good morning!"
    # Expected: ignored, returns (None, None)
    def test_unrelated_message_is_ignored(self):
        message = "Hey everyone, good morning!"
        print(f"\n[Test message] {repr(message)}")
        parsed, option = WordleParser.parse("Terence", message)
        self.assertIsNone(parsed)
        self.assertIsNone(option)


# ──────────────────────────────────────────────
#  WordleTracker tests  (Firebase mocked)
# ──────────────────────────────────────────────

class TestWordleTracker(unittest.TestCase):

    def setUp(self):
        """Create a WordleTracker with all Firebase calls mocked out."""
        with patch("firebase_admin.initialize_app"), \
             patch("firebase_admin.credentials.Certificate"), \
             patch("firebase_admin.firestore.client") as mock_firestore:
            self.mock_db = MagicMock()
            mock_firestore.return_value = self.mock_db
            self.tracker = WordleTracker()
            self.tracker.db = self.mock_db

    def _query_mock(self, docs):
        """Wire up the Firestore query chain to return the given list of docs."""
        self.mock_db.collection.return_value \
            .where.return_value \
            .where.return_value \
            .stream.return_value = docs

    def _single_where_mock(self, docs):
        """Wire up a single .where() chain (used by leaderboard)."""
        self.mock_db.collection.return_value \
            .where.return_value \
            .stream.return_value = docs

    # 2. Player submits a score they've already submitted
    # Data: Terence already has a score of 4/6 for puzzle 1738 in the database
    # Expected: duplicate detected, message contains player name and puzzle number
    def test_duplicate_check_detects_existing_entry(self):
        self._query_mock([make_firestore_doc("Terence", 4, 6)])
        parsed = (1738, "Terence", 4, 6, "2026-03-23", "March", "2026")
        print(f"\n[Test data] Player=Terence, Puzzle=1738, Score=4/6 (already in DB)")
        is_duplicate, message = self.tracker.duplicate_check(parsed)

        self.assertTrue(is_duplicate)
        self.assertIn("Terence", message)
        self.assertIn("1738", message)

    # New player submitting for the first time — should not be flagged
    # Data: no existing entry for Alice on puzzle 1738
    # Expected: not a duplicate
    def test_duplicate_check_passes_for_new_entry(self):
        self._query_mock([])
        parsed = (1738, "Alice", 3, 6, "2026-03-23", "March", "2026")
        print(f"\n[Test data] Player=Alice, Puzzle=1738 (no existing entry in DB)")
        is_duplicate, _ = self.tracker.duplicate_check(parsed)

        self.assertFalse(is_duplicate)

    # Player's original submission was a failed attempt (X/6)
    # Data: Terence has score=7 (X) stored for puzzle 1738
    # Expected: duplicate message shows "X/6" not a number
    def test_duplicate_check_shows_x_when_original_was_failed(self):
        self._query_mock([make_firestore_doc("Terence", 7, 6)])
        parsed = (1738, "Terence", 3, 6, "2026-03-23", "March", "2026")
        print(f"\n[Test data] Player=Terence, Puzzle=1738, Original score=X/6 (score=7 in DB)")
        _, message = self.tracker.duplicate_check(parsed)

        self.assertIn("X/6", message)

    # Daily leaderboard — players sorted by score ascending (lower = better)
    # Data: Alice=5/6, Bob=2/6, Carol=3/6
    # Expected: Bob, Carol, Alice
    def test_leaderboard_sorted_by_score(self):
        self._single_where_mock([
            make_firestore_doc("Alice", 5, 6),
            make_firestore_doc("Bob", 2, 6),
            make_firestore_doc("Carol", 3, 6),
        ])
        print(f"\n[Test data] Alice=5/6, Bob=2/6, Carol=3/6 — expected order: Bob, Carol, Alice")
        result = self.tracker.leaderboard(1738)
        lines = result.split("\n")

        self.assertIn("Bob", lines[1])
        self.assertIn("Carol", lines[2])
        self.assertIn("Alice", lines[3])

    # Leaderboard entry where player failed — score displayed as X/6
    # Data: Terence has score=7 (X) for puzzle 1738
    # Expected: leaderboard shows "X/6" for Terence
    def test_leaderboard_displays_x_for_failed_score(self):
        self._single_where_mock([make_firestore_doc("Terence", 7, 6)])
        print(f"\n[Test data] Player=Terence, Score=X/6 (stored as 7)")
        result = self.tracker.leaderboard(1738)

        self.assertIn("X/6", result)

    # Monthly totals — points accumulate across multiple puzzles
    # Data: Alice scores 2/6 and 3/6 = 9 pts, Bob scores 4/6 = 3 pts
    # Expected: Alice ranked first
    def test_monthly_totals_accumulated_across_puzzles(self):
        self._query_mock([
            make_firestore_doc("Alice", 2, 6),   # 6 - 2 + 1 = 5 pts
            make_firestore_doc("Alice", 3, 6),   # 6 - 3 + 1 = 4 pts  → Alice total = 9
            make_firestore_doc("Bob",   4, 6),   # 6 - 4 + 1 = 3 pts  → Bob total = 3
        ])
        print(f"\n[Test data] Alice: 2/6 + 3/6 = 9pts, Bob: 4/6 = 3pts — expected: Alice first")
        result = self.tracker.monthly_totals("March", "2026")
        lines = result.split("\n")

        self.assertIn("Alice", lines[1])
        self.assertIn("Bob", lines[2])

    # Monthly totals with no submissions for that month
    # Data: empty database for January 2026
    # Expected: only the header line is returned
    def test_monthly_totals_empty_returns_header_only(self):
        self._query_mock([])
        print(f"\n[Test data] No entries for January 2026")
        result = self.tracker.monthly_totals("January", "2026")
        non_empty_lines = [l for l in result.split("\n") if l.strip()]

        self.assertEqual(len(non_empty_lines), 1)  # just the header


if __name__ == "__main__":
    unittest.main(verbosity=2)
