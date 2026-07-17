"""Keep the in-app guide discoverable and complete as features grow."""

from pathlib import Path
import unittest


class HelpScreenSourceTests(unittest.TestCase):
    def test_guide_covers_primary_workflows(self) -> None:
        source = Path("mobile/screens/help_screen.py").read_text(encoding="utf-8")
        for phrase in (
            "Timer and countdown",
            "Categories and daily wins",
            "Create a goal",
            "Weekly resets on Monday",
            "Calendar, dashboard, and stats",
            "Insights and AI Coach",
            "Settings, data, and widgets",
        ):
            self.assertIn(phrase, source)

    def test_guide_is_available_from_more(self) -> None:
        source = Path("mobile/app_shell.py").read_text(encoding="utf-8")
        self.assertIn('("How to use", ft.Icons.HELP_OUTLINE, help_screen.build)', source)


if __name__ == "__main__":
    unittest.main()
