"""Unit tests for Dashboard SQLite Database."""

import tempfile
import unittest
from pathlib import Path

from dashboard_db import DashboardDB, DEFAULT_EXCEL_PATH


class TestDashboardDB(unittest.TestCase):
    def test_init_and_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test_dashboard.db"
            db = DashboardDB(excel_path=DEFAULT_EXCEL_PATH, db_path=temp_db)

            # Test DB initialization
            total = db.init_db(force_reload=True)
            self.assertEqual(total, 2999)
            self.assertTrue(temp_db.exists())

            # Test SQL query execution
            res = db.query("SELECT COUNT(*) as count FROM dashboard")
            self.assertEqual(res[0]["count"], 2999)

            # Test query with parameters
            plumber_res = db.query("SELECT COUNT(*) as count FROM dashboard WHERE servicio = ?", ("Plomero",))
            self.assertEqual(plumber_res[0]["count"], 141)

            # Test summary metrics
            metrics = db.get_summary_metrics()
            self.assertEqual(metrics["total_registros"], 2999)
            self.assertIn("F", metrics["distribucion_genero"])
            self.assertIn("M", metrics["distribucion_genero"])

    def test_read_only_safety(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test_dashboard.db"
            db = DashboardDB(excel_path=DEFAULT_EXCEL_PATH, db_path=temp_db)
            db.init_db()
            with self.assertRaises(sqlite3.OperationalError):
                db.query("DROP TABLE dashboard")


if __name__ == "__main__":
    unittest.main()
