"""Properties of the fixed-width fare readers, checked on generated input.

The fixture tests read the records someone thought to write. These read every
record Hypothesis can build inside the RSPS5045 widths, so a shifted offset or a
swapped day and month fails here even when no fixture holds the case.
"""

from __future__ import annotations

import string
import unittest
from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from trainbudget.fares.atoc_fare_declarations import _parse_dtd_date, format_pence
from trainbudget.fares.atoc_restrictions import parse_railcard_record

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
    @given(st.dates(min_value=date(1900, 1, 1), max_value=date(2999, 12, 31)))
    def test_a_written_date_reads_back_as_itself(self, day: date) -> None:
        self.assertEqual(_parse_dtd_date(day.strftime("%d%m%Y")), day)

    @given(st.text(max_size=12).filter(lambda value: value and not (len(value) == 8 and value.isdigit())))
    def test_anything_else_but_blank_is_refused_as_a_value_error(self, value: str) -> None:
        with self.assertRaises(ValueError):
            _parse_dtd_date(value)


class PenceTest(unittest.TestCase):
    @given(st.integers(min_value=0, max_value=10_000_000))
    def test_the_shown_price_reads_back_as_the_pence(self, pence: int) -> None:
        pounds, pennies = format_pence(pence)[1:].split(".")
        self.assertEqual(len(pennies), 2)
        self.assertEqual(int(pounds) * 100 + int(pennies), pence)


class RailcardRecordTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
