"""Tests for the RSPS5045 .RST restriction parser.

The sample lines are copied from the real DTD .RST file, so the field offsets
are checked against real records rather than only against the layout constants.
"""

from __future__ import annotations

import unittest

from atoc_restrictions import (
    RESTRICTION_WIDTHS,
    RestrictionIndex,
    parse_header,
    parse_railcard_record,
)

# The exact first record of each type in the real feeds/fares/dtd-fares.zip.
REAL_RH = (
    "RRHC0WOP LSE TO SOUTH WALES         PEAK TRAVEL RESTRICTIONS APPLY MON-FRI"
    "            PEAK TRAVEL RESTRICTIONS APPLY MON-FRI            NNY"
)
REAL_HD = "RHDC0W01040402YYYYYNN"
REAL_TR = "RTRC0W0001O04300703DEUSTAN"
REAL_TD = "RTDC0W0011O09291003YYYYYNN"
REAL_TT = "RTTC0W0001OLM"
REAL_RR = "RRRC00D00010AZ          Y"
REAL_SD = "RSDCBDL78996O08101031YYYYYNN"
REAL_SQ = "RSQC1AC04647RCLT A"
REAL_SR = "RSRC1AC04647RNN"
REAL_CA = "RCAC1STI      01020402YYYYYNN"
REAL_EC = "RECCAVALID IN SLEEPER ACCOMMODATION ONLY               "
REAL_RD = "RRDC0507202631102026"


class RestrictionParsingTest(unittest.TestCase):
    def test_the_real_record_widths_match_the_layout(self) -> None:
        self.assertEqual(RESTRICTION_WIDTHS["RH"], 139)
        self.assertEqual(RESTRICTION_WIDTHS["HD"], 21)
        self.assertEqual(RESTRICTION_WIDTHS["TR"], 26)
        self.assertEqual(RESTRICTION_WIDTHS["TD"], 26)
        self.assertEqual(RESTRICTION_WIDTHS["TT"], 13)
        self.assertEqual(RESTRICTION_WIDTHS["RR"], 25)
        self.assertEqual(RESTRICTION_WIDTHS["SD"], 28)
        self.assertEqual(RESTRICTION_WIDTHS["SQ"], 18)
        self.assertEqual(RESTRICTION_WIDTHS["SR"], 15)
        self.assertEqual(RESTRICTION_WIDTHS["CA"], 29)
        self.assertEqual(RESTRICTION_WIDTHS["EC"], 55)
        self.assertEqual(RESTRICTION_WIDTHS["RD"], 20)

    def test_parses_a_real_restriction_header(self) -> None:
        header = parse_header(REAL_RH)
        self.assertEqual(header.code, "0W")
        self.assertEqual(header.description, "OP LSE TO SOUTH WALES")
        self.assertEqual(header.outward_text, "PEAK TRAVEL RESTRICTIONS APPLY MON-FRI")
        self.assertEqual(header.return_text, "PEAK TRAVEL RESTRICTIONS APPLY MON-FRI")
        self.assertEqual(header.change_indicator, "Y")

    def test_parses_a_real_railcard_restriction_record(self) -> None:
        row = parse_railcard_record(REAL_RR)
        self.assertEqual(row.railcard_code, "00D")
        self.assertEqual(row.sequence_no, "0001")
        self.assertEqual(row.ticket_code, "0AZ")
        self.assertEqual(row.route_code, "")
        self.assertEqual(row.location, "")
        self.assertEqual(row.restriction_code, "")
        self.assertTrue(row.total_ban)

    def test_parses_a_railcard_restriction_code_row(self) -> None:
        # The Two Together railcard's first row carries restriction R9, not a ban.
        line = "RRRC2TR0001           R9 "
        row = parse_railcard_record(line)
        self.assertEqual(row.railcard_code, "2TR")
        self.assertEqual(row.restriction_code, "R9")
        self.assertFalse(row.total_ban)

    def test_indexes_every_real_record_type(self) -> None:
        index = RestrictionIndex()
        for line in (REAL_RH, REAL_HD, REAL_TR, REAL_TD, REAL_TT, REAL_RR, REAL_SD, REAL_SQ, REAL_SR, REAL_CA, REAL_EC, REAL_RD):
            index.load_line(line)
        self.assertEqual(index.rejected_records, 0)
        self.assertEqual(index.parsed_records, 12)
        self.assertEqual(
            set(index.record_counts),
            {"RH", "HD", "TR", "TD", "TT", "RR", "SD", "SQ", "SR", "CA", "EC", "RD"},
        )
        self.assertEqual(index.headers["0W"].description, "OP LSE TO SOUTH WALES")
        self.assertIn("0W", index.code_record_counts)
        self.assertIn("00D", index.railcard_record_counts)
        self.assertGreater(index.railcard_record_counts["00D"], 0)

    def test_a_comment_line_is_not_a_record(self) -> None:
        index = RestrictionIndex()
        index.load_line("/!! Start of file")
        self.assertEqual(index.parsed_records, 0)
        self.assertEqual(index.rejected_records, 0)

    def test_a_deleted_railcard_row_is_not_left_active(self) -> None:
        index = RestrictionIndex()
        index.load_line(REAL_RR)
        deleted = "D" + REAL_RR[1:]
        index.load_line(deleted)
        self.assertEqual(index.active_railcard_rows("00D"), [])
        self.assertNotIn("00D", index.railcard_record_counts)

    def test_an_unknown_record_type_is_rejected_and_blocks_publication(self) -> None:
        index = RestrictionIndex()
        index.files_read.append("rjfaf.rst")
        with self.assertRaises(ValueError):
            index.load_line("RXX" + " " * 22)
        self.assertEqual(index.unknown_types["XX"], 1)
        self.assertEqual(index.rejected_records, 1)
        self.assertIsNotNone(index.gate_problem())

    def test_a_truncated_record_is_rejected_rather_than_guessed(self) -> None:
        index = RestrictionIndex()
        index.files_read.append("rjfaf.rst")
        with self.assertRaises(ValueError):
            index.load_line("RTDC0W00")  # a TD record cut off after the code
        self.assertEqual(index.rejected_records, 1)

    def test_the_gate_refuses_when_no_restriction_file_loaded(self) -> None:
        index = RestrictionIndex()
        self.assertIsNotNone(index.gate_problem())

    def test_a_clean_index_passes_the_gate(self) -> None:
        index = RestrictionIndex()
        index.files_read.append("rjfaf.rst")
        index.load_line(REAL_RH)
        index.load_line(REAL_RR)
        self.assertIsNone(index.gate_problem())
        summary = index.summary()
        self.assertEqual(summary["files"], 1)
        self.assertEqual(summary["records"], 2)
        self.assertEqual(summary["rejected"], 0)
        self.assertEqual(summary["restriction_codes"], 1)
        self.assertEqual(summary["railcard_codes"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
