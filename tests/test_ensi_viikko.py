"""Tests for merging next week's menu. Run: python3 -m unittest discover tests"""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "kouluruoka" / "parser.py"
_SPEC = importlib.util.spec_from_file_location("kouluruoka_parser", _PATH)
parser = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(parser)


def _meal(name):
    return {"MealType": "Lounas", "Name": name, "Items": []}


def _menu(days):
    return {"result": {"pageContext": {"menu": {
        "RestaurantName": "Esimerkkikoulu",
        "Days": [{"Date": label, "Meals": [_meal(name)]} for label, name in days],
    }}}}


THIS_WEEK = _menu([("torstai 26.11.", "Kalakeitto"), ("perjantai 27.11.", "Pinaattiletut")])
NEXT_WEEK = _menu([
    ("maanantai 30.11.", "Jauhelihakastike"),
    ("tiistai 1.12.", "Broileririisi"),
    ("perjantai 4.12.", "Pizza"),
])
WEEK_AFTER = _menu([("perjantai 11.12.", "Makaronilaatikko")])


def _names(menu):
    return [d["Date"] for d in menu["result"]["pageContext"]["menu"]["Days"]]


class MergeMenuDaysTest(unittest.TestCase):
    def test_appends_next_week(self):
        merged = parser.merge_menu_days(_menu([("perjantai 27.11.", "A")]), NEXT_WEEK)
        self.assertEqual(
            _names(merged),
            ["perjantai 27.11.", "maanantai 30.11.", "tiistai 1.12.", "perjantai 4.12."],
        )

    def test_current_week_wins_on_same_day(self):
        merged = parser.merge_menu_days(
            _menu([("perjantai 27.11.", "Tämä")]), _menu([("perjantai 27.11.", "Toinen")])
        )
        days = merged["result"]["pageContext"]["menu"]["Days"]
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]["Meals"][0]["Name"], "Tämä")

    def test_missing_next_week_keeps_menu(self):
        menu = _menu([("perjantai 27.11.", "A")])
        self.assertEqual(_names(parser.merge_menu_days(menu, None)), ["perjantai 27.11."])

    def test_weekend_tomorrow_comes_from_next_week(self):
        menu = parser.merge_menu_days(_menu(list(
            (d["Date"], d["Meals"][0]["Name"])
            for d in THIS_WEEK["result"]["pageContext"]["menu"]["Days"]
        )), NEXT_WEEK)
        snap, _ = parser.build_snapshot(menu, {}, date(2026, 11, 29))  # sunday
        self.assertEqual(snap["lounas_huomenna"], "Jauhelihakastike")
        self.assertIn(date(2026, 11, 30), [d["date"] for d in snap["calendar"]])


class MealsForDateTest(unittest.TestCase):
    def test_day_is_not_matched_by_substring(self):
        menu = parser.merge_menu_days(_menu([("tiistai 1.12.", "Broileririisi")]), WEEK_AFTER)
        meals = parser.meals_for_date(menu, date(2026, 12, 1))
        self.assertEqual(meals["lounas"]["name"], "Broileririisi")


if __name__ == "__main__":
    unittest.main()
