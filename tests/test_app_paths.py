import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app_paths import app_home, default_database_url


class AppPathsTests(unittest.TestCase):
    def test_app_home_uses_override_when_present(self) -> None:
        with patch.dict(os.environ, {"ZONES_HOME": r"C:\Temp\ZonesHome"}, clear=False):
            self.assertEqual(app_home(), Path(r"C:\Temp\ZonesHome"))

    def test_default_database_url_points_to_sqlite_file(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            database_url = default_database_url()
        self.assertTrue(database_url.startswith("sqlite:///"))
        self.assertIn("zones.db", database_url)


if __name__ == "__main__":
    unittest.main()
