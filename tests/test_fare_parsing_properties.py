"""Properties of the fixed-width fare readers, checked on generated input.

The fixture tests read the records someone thought to write. These read every
record Hypothesis can build inside the RSPS5045 widths, so a shifted offset or a
swapped day and month fails here even when no fixture holds the case.
"""

from __future__ import annotations

import string
import tempfile
import unittest
from datetime import date
from pathlib import Path
from fractions import Fraction

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from trainbudget.fares.atoc_fares import FaresDb
from trainbudget.feeds.make_synthetic_feed import build_synthetic_feed
from trainbudget.fares.atoc_fare_declarations import (
    RAILCARD_DISCOUNT,
    ROUNDING_STEP_PENCE,
    _parse_dtd_date,
    _round_down_to,
    format_pence,
)
from trainbudget.fares.atoc_restrictions import parse_railcard_record

#: Time-based checks fail a loaded runner, not the parser: verify --fast runs
#: these beside 300 other tests, and on 29 October 2026 that tripped too_slow.
STEADY = settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])

#: Each example prices the whole fixture twice; twenty-five is enough to shake
#: out an off-by-one in the budget filter without turning the unit run into a
#: scale test.
BUDGET = settings(
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    max_examples=25,
)
FIELD_TEXT = string.ascii_uppercase + string.digits

#: RSPS5045's RR record, written out here rather than read from the parser, so a
#: parser whose own table drifts is read against the specification.
RR_COLUMNS = (
    ("update_marker", 1),
    ("record_type", 2),
    ("cf_marker", 1),
    ("railcard_code", 3),
    ("sequence_no", 4),
    ("ticket_code", 3),
    ("route_code", 5),
    ("location", 3),
    ("restriction_code", 2),
    ("total_ban", 1),
)


def _field(width: int) -> st.SearchStrategy[str]:
    return st.text(FIELD_TEXT, min_size=0, max_size=width)


class DtdDateTest(unittest.TestCase):
    @STEADY
    @given(st.dates(min_value=date(1900, 1, 1), max_value=date(2999, 12, 31)))
    def test_a_written_date_reads_back_as_itself(self, day: date) -> None:
        self.assertEqual(_parse_dtd_date(day.strftime("%d%m%Y")), day)

    @STEADY
    @given(st.text(max_size=12).filter(lambda value: value and not (len(value) == 8 and value.isdigit())))
    def test_anything_else_but_blank_is_refused_as_a_value_error(self, value: str) -> None:
        with self.assertRaises(ValueError):
            _parse_dtd_date(value)


class PenceTest(unittest.TestCase):
    @STEADY
    @given(st.integers(min_value=0, max_value=10_000_000))
    def test_the_shown_price_reads_back_as_the_pence(self, pence: int) -> None:
        pounds, pennies = format_pence(pence)[1:].split(".")
        self.assertEqual(len(pennies), 2)
        self.assertEqual(int(pounds) * 100 + int(pennies), pence)


class RailcardRecordTest(unittest.TestCase):
    @STEADY
    @given(
        st.fixed_dictionaries(
            {
                name: _field(width)
                for name, width in RR_COLUMNS
                if name not in {"record_type", "total_ban"}
            }
        ),
        st.sampled_from(["Y", "N", " "]),
    )
    def test_each_field_reads_back_from_its_own_columns(self, fields: dict[str, str], ban: str) -> None:
        values = {**fields, "record_type": "RR", "total_ban": ban}
        line = "".join(values[name].ljust(width) for name, width in RR_COLUMNS)
        row = parse_railcard_record(line)
        self.assertEqual(
            (row.railcard_code, row.sequence_no, row.ticket_code, row.route_code, row.location,
             row.restriction_code, row.current_or_future, row.update_marker, row.total_ban),
            (fields["railcard_code"], fields["sequence_no"], fields["ticket_code"], fields["route_code"],
             fields["location"], fields["restriction_code"], fields["cf_marker"], fields["update_marker"],
             ban == "Y"),
        )



class _Pricer(FaresDb):
    """A database whose discount and minimum are the two values a property sets.

    ``railcard_price`` reads those two through the database, so a stand-in that
    answers them directly checks the price arithmetic without a feed.
    """

    def __init__(self, discount: Fraction | None, minimum: int | None) -> None:
        self._discount = discount
        self._minimum = minimum

    def railcard_discount(self, railcard_code: str, ticket_code: str, day: date | None = None) -> Fraction | None:
        return self._discount

    def minimum_fare(self, railcard_code: str, ticket_code: str, day: date | None = None) -> int | None:
        return self._minimum


class RailcardPriceTest(unittest.TestCase):
    @STEADY
    @given(st.integers(min_value=0, max_value=1_000_000))
    def test_rounding_lands_on_the_step_at_or_below_the_value(self, pence: int) -> None:
        rounded = _round_down_to(Fraction(pence), ROUNDING_STEP_PENCE)
        self.assertEqual(rounded % ROUNDING_STEP_PENCE, 0)
        self.assertLessEqual(rounded, pence)
        self.assertLess(pence - rounded, ROUNDING_STEP_PENCE)

    @STEADY
    @given(
        st.integers(min_value=0, max_value=1_000_000),
        st.integers(min_value=0, max_value=1_000_000),
    )
    def test_no_discount_returns_the_standard_fare_and_ignores_the_minimum(
        self, standard: int, minimum: int
    ) -> None:
        price = _Pricer(None, minimum).railcard_price("ABC", "TST", standard)
        self.assertEqual(price, standard)

    @STEADY
    @given(
        st.integers(min_value=0, max_value=1_000_000),
        st.integers(min_value=1, max_value=99),
        st.none() | st.integers(min_value=0, max_value=40_000).map(lambda n: n * ROUNDING_STEP_PENCE),
    )
    def test_a_discount_never_costs_more_than_the_standard_fare(
        self, standard: int, percent: int, minimum: int | None
    ) -> None:
        if minimum is not None:
            standard = max(standard, minimum)
        price = _Pricer(Fraction(percent, 100), minimum).railcard_price("ABC", "TST", standard)
        self.assertLessEqual(price, standard)
        self.assertEqual(price % ROUNDING_STEP_PENCE, 0)

    @STEADY
    @given(
        st.integers(min_value=0, max_value=1_000_000),
        st.integers(min_value=1, max_value=99),
        st.integers(min_value=0, max_value=40_000).map(lambda n: n * ROUNDING_STEP_PENCE),
    )
    def test_the_minimum_is_a_floor_on_a_discounted_fare(
        self, standard: int, percent: int, minimum: int
    ) -> None:
        price = _Pricer(Fraction(percent, 100), minimum).railcard_price("ABC", "TST", standard)
        self.assertGreaterEqual(price, minimum)

    def test_a_pair_with_no_record_is_read_as_a_third_off(self) -> None:
        self.assertEqual(FaresDb().railcard_discount("NOPE", "NOPE"), 1 - RAILCARD_DISCOUNT)



class BudgetMonotonicityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        feed = build_synthetic_feed(
            Path(cls._tmp.name) / "fares", include_restrictions=True
        )
        cls.db = FaresDb().load_feed(feed)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    @BUDGET
    @given(st.integers(min_value=0, max_value=5_000), st.integers(min_value=0, max_value=5_000))
    def test_a_larger_budget_keeps_every_destination(self, low: int, extra: int) -> None:
        cheap = {row.crs for row in self.db.priced_destinations_within("GRN", low)}
        dearer = {
            row.crs for row in self.db.priced_destinations_within("GRN", low + extra)
        }
        self.assertLessEqual(cheap, dearer)


if __name__ == "__main__":
    unittest.main()
