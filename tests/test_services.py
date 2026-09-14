from datetime import datetime, timezone
import os
import sys
import unittest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "custom_components", "ista")
    ),
)
from coordinator import select_receipt_to_download


class TestSelectReceiptToDownload(unittest.TestCase):
    """Tests for selecting the appropriate receipt for download."""

    def setUp(self):
        self.sample_data = {
            "hot_water": {
                "latest_receipt": {
                    "receipt_id": "hw_latest_123",
                    "date": "10/08/2026",
                    "type": "Recibo de Agua caliente",
                    "amount": 49.27,
                }
            },
            "heating": {
                "latest_receipt": {
                    "receipt_id": "heat_latest_456",
                    "date": "30/05/2026",
                    "type": "Recibo optosonic 3",
                    "amount": 61.47,
                }
            },
            "receipts": [
                {
                    "receipt_id": "hw_latest_123",
                    "date": "10/08/2026",
                    "type": "Recibo de Agua caliente",
                    "amount": 49.27,
                },
                {
                    "receipt_id": "heat_latest_456",
                    "date": "30/05/2026",
                    "type": "Recibo optosonic 3",
                    "amount": 61.47,
                },
                {
                    "receipt_id": "hw_older_789",
                    "date": "10/07/2026",
                    "type": "Recibo de Agua caliente",
                    "amount": 35.10,
                },
            ],
        }

    def test_default_picks_most_recent_of_the_two(self):
        """Default (latest) should pick the most recent between hot water and heating."""
        # Here hot water is 10/08/2026 and heating is 30/05/2026 -> should pick hot water
        selected = select_receipt_to_download(self.sample_data, invoice_type=None)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["receipt_id"], "hw_latest_123")

        selected_latest = select_receipt_to_download(self.sample_data, invoice_type="latest")
        self.assertIsNotNone(selected_latest)
        self.assertEqual(selected_latest["receipt_id"], "hw_latest_123")

        # Now make heating newer (e.g. 15/09/2026) -> should pick heating
        data_heating_newer = {
            "hot_water": {
                "latest_receipt": {
                    "receipt_id": "hw_latest_123",
                    "date": "10/08/2026",
                    "type": "Recibo de Agua caliente",
                    "amount": 49.27,
                }
            },
            "heating": {
                "latest_receipt": {
                    "receipt_id": "heat_newest_999",
                    "date": "15/09/2026",
                    "type": "Recibo optosonic 3",
                    "amount": 75.00,
                }
            },
            "receipts": [],
        }
        selected_heating_new = select_receipt_to_download(data_heating_newer, invoice_type="latest")
        self.assertIsNotNone(selected_heating_new)
        self.assertEqual(selected_heating_new["receipt_id"], "heat_newest_999")

    def test_filter_hot_water(self):
        """Selecting hot water should return the hot water receipt even if heating is newer."""
        data_heating_newer = {
            "hot_water": {
                "latest_receipt": {
                    "receipt_id": "hw_latest_123",
                    "date": "10/08/2026",
                    "type": "Recibo de Agua caliente",
                    "amount": 49.27,
                }
            },
            "heating": {
                "latest_receipt": {
                    "receipt_id": "heat_newest_999",
                    "date": "15/09/2026",
                    "type": "Recibo optosonic 3",
                    "amount": 75.00,
                }
            },
            "receipts": [],
        }
        for alias in ["hot_water", "agua caliente", "caliente", "agua", "acs"]:
            selected = select_receipt_to_download(data_heating_newer, invoice_type=alias)
            self.assertIsNotNone(selected, f"Failed for alias: {alias}")
            self.assertEqual(selected["receipt_id"], "hw_latest_123")

    def test_filter_heating(self):
        """Selecting heating should return the heating receipt even if hot water is newer."""
        for alias in ["heating", "calefaccion", "calefacción", "calor", "optosonic"]:
            selected = select_receipt_to_download(self.sample_data, invoice_type=alias)
            self.assertIsNotNone(selected, f"Failed for alias: {alias}")
            self.assertEqual(selected["receipt_id"], "heat_latest_456")

    def test_explicit_receipt_id_override(self):
        """Passing receipt_id should override invoice_type."""
        selected = select_receipt_to_download(
            self.sample_data,
            invoice_type="hot_water",
            receipt_id="heat_latest_456",
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected["receipt_id"], "heat_latest_456")

        # Unknown receipt_id still returns minimal dict with that ID
        selected_unknown = select_receipt_to_download(
            self.sample_data,
            receipt_id="unknown_id_xyz",
        )
        self.assertIsNotNone(selected_unknown)
        self.assertEqual(selected_unknown["receipt_id"], "unknown_id_xyz")


if __name__ == "__main__":
    unittest.main()
