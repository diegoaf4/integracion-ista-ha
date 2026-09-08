import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "custom_components", "ista")))
from ista_client import IstaClient, IstaAuthError


class TestIstaClient(unittest.TestCase):
    """Test suite for IstaClient."""

    def test_parse_number(self):
        """Test number parsing from Spanish formatted strings with units."""
        # Simple decimals
        self.assertEqual(IstaClient.parse_number("38.539"), 38.539)
        self.assertEqual(IstaClient.parse_number("49,27"), 49.27)

        # Numbers with unit strings and whitespace
        self.assertEqual(IstaClient.parse_number("37\xa0\r\n m3"), 37.0)
        self.assertEqual(IstaClient.parse_number("5\xa0\r\n m3"), 5.0)
        self.assertEqual(IstaClient.parse_number("55193\xa0\r\n KWh"), 55193.0)
        self.assertEqual(IstaClient.parse_number("669\xa0\r\n KWh"), 669.0)
        self.assertEqual(IstaClient.parse_number("136,09 €"), 136.09)

        # None / empty strings
        self.assertIsNone(IstaClient.parse_number(""))
        self.assertIsNone(IstaClient.parse_number(None))
        self.assertIsNone(IstaClient.parse_number("No data"))

    def test_live_login_and_fetch(self):
        """Integration test against real portal if credentials are provided in environment."""
        username = os.environ.get("ISTA_USERNAME")
        password = os.environ.get("ISTA_PASSWORD")
        if not username or not password:
            self.skipTest("ISTA_USERNAME and ISTA_PASSWORD not set in environment")

        client = IstaClient(username, password)
        data = client.fetch_data()

        # Check account
        self.assertIn("name", data["account"])
        self.assertIn("subscriber_number", data["account"])

        # Check hot water
        hw = data["hot_water"]
        self.assertIn("current_reading", hw)
        self.assertGreater(hw["current_reading"], 0)
        self.assertEqual(hw["unit"], "m3")
        self.assertIn("latest_receipt", hw)
        self.assertGreater(hw["latest_receipt"]["amount"], 0)

        # Check heating
        heating = data["heating"]
        self.assertIn("current_reading", heating)
        self.assertGreater(heating["current_reading"], 0)
        self.assertIn("latest_receipt", heating)

        # Check receipts
        self.assertGreater(len(data["receipts"]), 0)

        # Check PDF download of latest receipt
        latest_rec_id = data["receipts"][0].get("receipt_id")
        if latest_rec_id:
            pdf_bytes = client.download_receipt_pdf(latest_rec_id)
            self.assertGreater(len(pdf_bytes), 1000)
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
