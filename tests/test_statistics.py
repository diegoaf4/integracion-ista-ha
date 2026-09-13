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
from statistics import (
    extract_historical_cost_datapoints,
    extract_historical_datapoints,
    parse_flexible_date,
)


class TestIstaStatistics(unittest.TestCase):
    """Tests for statistics date parsing, history extraction, and cost calculations."""

    def test_parse_flexible_date_standard(self):
        """Test parsing of standard date formats."""
        dt1 = parse_flexible_date("15/03/2026", tz=timezone.utc)
        self.assertIsNotNone(dt1)
        self.assertEqual(dt1.year, 2026)
        self.assertEqual(dt1.month, 3)
        self.assertEqual(dt1.day, 15)

        dt2 = parse_flexible_date("2026-01-31", tz=timezone.utc)
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.year, 2026)
        self.assertEqual(dt2.month, 1)
        self.assertEqual(dt2.day, 31)

    def test_parse_flexible_date_spanish_months(self):
        """Test parsing of dates with Spanish month names."""
        dt = parse_flexible_date("Enero 2026", tz=timezone.utc)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 1)

        dt2 = parse_flexible_date("15 Febrero 2026", tz=timezone.utc)
        self.assertIsNotNone(dt2)
        self.assertEqual(dt2.year, 2026)
        self.assertEqual(dt2.month, 2)
        self.assertEqual(dt2.day, 15)

    def test_extract_historical_datapoints(self):
        """Test extraction, sorting, and deduplication of historical readings."""
        group_data = {
            "serial": "123456",
            "unit": "m3",
            "current_reading": 42.5,
            "current_reading_date": "20/03/2026",
            "monthly_history": [
                {
                    "date": "31/01/2026",
                    "previous_reading": 35.0,
                    "current_reading": 38.0,
                    "consumption": 3.0,
                },
                {
                    "date": "28/02/2026",
                    "previous_reading": 38.0,
                    "current_reading": 40.0,
                    "consumption": 2.0,
                },
            ],
            "daily_readings": {
                "01/03/2026": 40.2,
                "02/03/2026": 40.5,
                "03/03/2026": 40.8,
            },
        }

        datapoints = extract_historical_datapoints(group_data, tz=timezone.utc)

        # Expect chronological order: 31/01, 28/02, 01/03, 02/03, 03/03, 20/03
        self.assertEqual(len(datapoints), 6)

        readings = [val for _, val, _ in datapoints]
        self.assertEqual(readings, [38.0, 40.0, 40.2, 40.5, 40.8, 42.5])

        # Verify cumulative sums are strictly monotonic
        sums = [cum for _, _, cum in datapoints]
        self.assertEqual(sums, [3.0, 5.0, 5.2, 5.5, 5.8, 7.5])

        # Verify timestamps are strictly increasing
        timestamps = [dt for dt, _, _ in datapoints]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_meter_replacement_continuity(self):
        """Test that meter replacements do not drop new meter readings and accumulate sum correctly."""
        group_data = {
            "serial": "537204735",
            "unit": "m3",
            "current_reading": 38.539,
            "current_reading_date": "06/09/2026",
            "monthly_history": [
                {
                    "serial": "847240102",
                    "date": "10/12/2025",
                    "previous_reading": 316.0,
                    "current_reading": 323.0,
                    "consumption": 7.0,
                    "incidence": "Cierre equipo y modulo mobile",
                },
                {
                    "serial": "537204735",
                    "date": "10/01/2026",
                    "previous_reading": 0.0,
                    "current_reading": 8.0,
                    "consumption": 8.0,
                    "incidence": "Sin incidencia",
                },
                {
                    "serial": "537204735",
                    "date": "10/02/2026",
                    "previous_reading": 8.0,
                    "current_reading": 13.0,
                    "consumption": 5.0,
                    "incidence": "Sin incidencia",
                },
            ],
            "daily_readings": {
                "05/09/2026": 38.5,
                "06/09/2026": 38.539,
            },
        }

        datapoints = extract_historical_datapoints(group_data, tz=timezone.utc)
        self.assertEqual(len(datapoints), 5)

        # Readings should track physical dials (including the drop when replaced)
        readings = [val for _, val, _ in datapoints]
        self.assertEqual(readings, [323.0, 8.0, 13.0, 38.5, 38.539])

        # Sum must remain strictly non-decreasing across meter change
        cumulative_sums = [cum for _, _, cum in datapoints]
        self.assertEqual(cumulative_sums, [7.0, 15.0, 20.0, 45.5, 45.539])
        for i in range(1, len(cumulative_sums)):
            self.assertGreaterEqual(cumulative_sums[i], cumulative_sums[i - 1])

    def test_estimated_cost_calculation(self):
        """Test unbilled cost calculation logic."""
        # Case 1: Automatic from latest invoice
        unbilled_consumption = 3.5  # m3
        last_billed_consumption = 5.0  # m3
        latest_invoice_amount = 75.00  # EUR

        unit_price = round(latest_invoice_amount / last_billed_consumption, 4)
        estimated_cost = round(unbilled_consumption * unit_price, 2)

        self.assertEqual(unit_price, 15.0)
        self.assertEqual(estimated_cost, 52.50)

        # Case 2: Configured manual price override
        manual_price = 18.50
        manual_cost = round(unbilled_consumption * manual_price, 2)
        self.assertEqual(manual_cost, 64.75)

    def test_extract_historical_cost_datapoints(self):
        """Test historical invoice cost extraction and cumulative sum calculation."""
        receipts = [
            {"date": "10/03/2026", "type": "Agua caliente", "amount": 30.00, "receipt_id": "r3"},
            {"date": "10/01/2026", "type": "Agua caliente", "amount": 25.50, "receipt_id": "r1"},
            {"date": "10/02/2026", "type": "Agua caliente", "amount": 20.00, "receipt_id": "r2"},
            {"date": "10/01/2026", "type": "Optosonic", "amount": 60.00, "receipt_id": "r4"},
            {"date": "10/02/2026", "type": "Calefacción", "amount": 80.00, "receipt_id": "r5"},
        ]

        # Hot water cost series
        hw_series = extract_historical_cost_datapoints(receipts, "hot_water", tz=timezone.utc)
        self.assertEqual(len(hw_series), 3)

        # Chronological order: 10/01 (25.50), 10/02 (20.00 -> cum 45.50), 10/03 (30.00 -> cum 75.50)
        amounts = [amt for _, amt, _ in hw_series]
        cumulative = [cum for _, _, cum in hw_series]

        self.assertEqual(amounts, [25.50, 20.00, 30.00])
        self.assertEqual(cumulative, [25.50, 45.50, 75.50])

        # Heating cost series
        heating_series = extract_historical_cost_datapoints(receipts, "heating", tz=timezone.utc)
        self.assertEqual(len(heating_series), 2)
        heating_cum = [cum for _, _, cum in heating_series]
        self.assertEqual(heating_cum, [60.00, 140.00])


if __name__ == "__main__":
    unittest.main()

