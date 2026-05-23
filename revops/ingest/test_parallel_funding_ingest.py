#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from parallel_funding_ingest import parse_latest_round, parse_usd, row_value  # noqa: E402


class FundingIngestParsingTest(unittest.TestCase):
    def test_parse_usd_accepts_long_and_shorthand_units(self) -> None:
        self.assertEqual(parse_usd("$285M"), 285_000_000)
        self.assertEqual(parse_usd("$2.3B"), 2_300_000_000)
        self.assertEqual(parse_usd("$2.3 billion"), 2_300_000_000)
        self.assertEqual(parse_usd("285000000"), 285_000_000)

    def test_parse_latest_round_handles_shorthand_valuation(self) -> None:
        fact = parse_latest_round("['Series E $950M at $15.8B valuation, May 2026']")
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact.stage, "Series E")
        self.assertEqual(fact.amount_usd, 950_000_000)
        self.assertEqual(fact.valuation_usd, 15_800_000_000)
        self.assertEqual(fact.occurred_on.isoformat(), "2026-05-01")

    def test_parse_latest_round_handles_long_form_valuation(self) -> None:
        fact = parse_latest_round("['Series C $175 million at $4.5 billion valuation, Oct 28, 2024']")
        self.assertIsNotNone(fact)
        assert fact is not None
        self.assertEqual(fact.stage, "Series C")
        self.assertEqual(fact.amount_usd, 175_000_000)
        self.assertEqual(fact.valuation_usd, 4_500_000_000)
        self.assertEqual(fact.occurred_on.isoformat(), "2024-10-28")

    def test_row_value_accepts_alternate_headers(self) -> None:
        row = {"company_domain": "example.com", "company_name": "Example"}
        self.assertEqual(row_value(row, "domain", "company_domain"), "example.com")
        self.assertEqual(row_value(row, "company", "company_name"), "Example")
        self.assertEqual(row_value(row, "missing"), "")


if __name__ == "__main__":
    unittest.main()
