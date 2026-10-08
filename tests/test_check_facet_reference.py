"""Tests for the check that keeps the facet reference data true to the registry.

The check exists because a generated file went stale in silence: three shipped
facet sources were absent from the checked-in copy and nothing failed. So the
tests are about the two ways the check itself can be wrong. It can miss drift,
which is the failure it was written for. It can also report drift that is not
there, which is worse than it sounds: a check that cries wolf about the path it
was pointed at, or about a facet it was told not to read, is a check somebody
turns off, and then it misses drift again.

The comparison is a pure function, so that is what these tests call. The
regeneration itself is not exercised here: it reads the real fares feed, and a
unit suite that downloaded a feed would be a suite nobody runs.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import check_facet_reference
from tools.check_facet_reference import CODES_SHOWN, compare, facet_stations, main


def payload(
    facets: dict[str, list[str]] | None = None,
    *,
    stations: int = 3436,
    schema: int = 2,
    feed: str = "feeds/fares/dtd-fares.zip",
    source: str = "a location source",
    supported: list[str] | None = None,
    sources: dict[str, dict[str, str]] | None = None,
) -> dict:
    """A reference payload in the shape the regenerator writes.

    The registry entry for each facet is derived from the facets the station
    mapping uses, so a test that moves one station sees exactly one difference,
    and a test about the registry has to say which part of it it is changing.
    """
    keys = sorted({key for entries in (facets or {}).values() for key in entries})
    if supported is None:
        supported = keys
    if sources is None:
        # Derived from the registry rather than from the mapping, because the two
        # sides of a test are allowed to hold different facets: a facet the
        # registry declares and no station carries is still a registry entry.
        sources = {
            key: {
                "name": f"the {key} source",
                "url": f"https://example.org/{key}",
                "coverage": "somewhere",
            }
            for key in supported
        }
    return {
        "schema": schema,
        "source": source,
        "feed": feed,
        "stations": stations,
        "facetSources": sources,
        "supportedFacets": list(supported),
        "facets": {crs: sorted(entries) for crs, entries in sorted((facets or {}).items())},
    }


class FacetStationsTest(unittest.TestCase):
    def test_a_station_is_recorded_under_every_facet_it_carries(self) -> None:
        # The mapping is read from the file's own shape, which is one record per
        # station listing its facets. Reading it as a facet-to-stations map is
        # this check's first job, and a station tagged twice must appear twice.
        # The whole payload, not the mapping alone: `facet_stations` reads the
        # `facets` key of a reference file, so a bare mapping reads as a file
        # with no records and every assertion below would pass against nothing.
        per = facet_stations(
            {"facets": {"SEV": ["town", "nature", "national_trust"], "PFL": ["rspb"]}}
        )
        self.assertEqual(per["national_trust"], {"SEV"})
        self.assertEqual(per["rspb"], {"PFL"})
        self.assertEqual(per["town"], {"SEV"})

    def test_a_file_with_no_records_has_no_facets_rather_than_an_empty_one(self) -> None:
        self.assertEqual(facet_stations({"schema": 2, "facets": {}}), {})


class ComparisonTest(unittest.TestCase):
    def test_a_checked_in_copy_that_matches_the_registry_is_not_drift(self) -> None:
        same = {"BEM": ["rspb"], "SOC": ["seaside"]}
        result = compare(payload(same), payload(same))
        self.assertEqual(result.moved, 0)
        self.assertEqual(result.lines, [])
        self.assertEqual(result.unreadable, [])

    def test_a_facet_that_lost_a_station_names_the_code_it_lost(self) -> None:
        # The ADR-0063 prune dropped five heritage stations on the real file, and
        # an operator reading a failure needs the codes rather than a count.
        result = compare(
            payload({"BDI": ["heritage"], "BUX": ["heritage"], "LUT": ["heritage"]}),
            payload({"LUT": ["heritage"]}),
        )
        self.assertEqual(result.moved, 1)
        self.assertEqual(len(result.lines), 1)
        self.assertIn("facet heritage: 3 in the checked-in copy, 1 regenerated", result.lines[0])
        self.assertIn("removed BDI, BUX", result.lines[0])

    def test_a_facet_that_gained_a_station_names_the_code_it_gained(self) -> None:
        result = compare(
            payload({"TEN": ["seaside"]}),
            payload({"TEN": ["seaside"], "EDL": ["seaside"]}),
        )
        self.assertEqual(result.moved, 1)
        self.assertIn("added EDL", result.lines[0])

    def test_a_source_that_shipped_without_regenerating_the_file_is_drift(self) -> None:
        # This is the failure the check exists for: the registry gained a facet,
        # the checked-in copy has no station for it, and the build reads the file.
        result = compare(
            payload({"TEN": ["seaside"]}),
            payload({"TEN": ["seaside"], "EDL": ["national_park"]}),
        )
        moved = [line for line in result.lines if line.startswith("facet ")]
        self.assertEqual(moved, ["facet national_park: 0 in the checked-in copy, 1 regenerated; added EDL"])
        self.assertEqual(result.moved, 1)
        # The same facet is also new to the registry's own lists, and both are the
        # same drift: a source shipped and the file was not regenerated.
        self.assertIn(
            "supportedFacets: national_park is regenerated and the checked-in copy has no such facet",
            result.lines,
        )
        self.assertEqual(result.unreadable, [])

    def test_a_facet_whose_source_did_not_answer_is_not_reported_as_movement(self) -> None:
        # A regeneration that lost a facet would otherwise read as "the registry
        # removed nine stations", which sends the reader after a change nobody made.
        result = compare(
            payload({"BEM": ["rspb"], "PFL": ["rspb"]}),
            payload({}, supported=["rspb"]),
        )
        self.assertEqual(result.moved, 0)
        self.assertEqual(result.unreadable, ["rspb"])
        self.assertEqual(
            [line for line in result.lines if "facet rspb" in line],
            [],
            "an unread facet must not also be reported as a moved one",
        )

    def test_a_kept_facet_is_not_compared_and_is_named_as_kept(self) -> None:
        # `--keep-unavailable` is for a source that is unreachable today. The
        # regeneration never read that facet, so its stations cannot be compared
        # with the file's; reporting them as moved would make the flag useless.
        result = compare(
            payload({"AVN": ["heritage"], "LUT": ["heritage"]}),
            payload({}, supported=["heritage"]),
            frozenset({"heritage"}),
        )
        self.assertEqual(result.moved, 0)
        self.assertEqual(result.unreadable, [])
        self.assertEqual(result.kept, ["heritage"])

    def test_a_kept_facet_that_changed_its_registry_entry_is_still_drift(self) -> None:
        # The stations of a kept facet are unknown this run. Its url, name and
        # coverage are not: they come from the registry itself, so a facet that
        # changed its source is caught whether or not that source answered.
        before = payload({"AVN": ["heritage"]})
        after = payload({"AVN": ["heritage"]})
        after["facetSources"]["heritage"]["url"] = "https://example.org/moved"
        result = compare(before, after, frozenset({"heritage"}))
        self.assertEqual(result.moved, 0)
        self.assertEqual(len(result.lines), 1)
        self.assertIn("facetSources.heritage.url", result.lines[0])
        self.assertIn("https://example.org/moved", result.lines[0])

    def test_a_registry_that_declares_a_facet_the_file_does_not_have_is_drift(self) -> None:
        result = compare(
            payload({"TEN": ["seaside"]}, supported=["seaside"]),
            payload({"TEN": ["seaside"]}, supported=["seaside", "transport"]),
        )
        self.assertIn(
            "supportedFacets: transport is regenerated and the checked-in copy has no such facet",
            result.lines,
        )

    def test_a_facet_the_registry_no_longer_declares_is_drift(self) -> None:
        result = compare(
            payload({"TEN": ["seaside"]}, supported=["seaside", "transport"]),
            payload({"TEN": ["seaside"]}, supported=["seaside"]),
        )
        self.assertIn(
            "supportedFacets: transport is in the checked-in copy and the registry no longer declares it",
            result.lines,
        )

    def test_the_feed_path_and_the_source_constant_are_not_drift(self) -> None:
        # The check is pointed at whichever feed the caller chose, and the
        # `source` field is the regenerator's own constant. Neither is a claim
        # about the registry, so neither may fail a release: a check that fails
        # on an absolute feed path is a check that gets switched off.
        result = compare(
            payload(
                {"TEN": ["seaside"]},
                feed="/somewhere/else/dtd-fares.zip",
                source="a source named differently",
            ),
            payload({"TEN": ["seaside"]}),
        )
        self.assertEqual(result.lines, [], "the feed path and the source constant are not the registry")

    def test_the_station_count_and_schema_are_compared(self) -> None:
        # The station count is how many stations the feed's LOC file held, so two
        # different feeds are two different files, and the schema is what a reader
        # of the file relies on to interpret it.
        result = compare(payload({"TEN": ["seaside"]}, stations=3436), payload({"TEN": ["seaside"]}, stations=3301))
        self.assertIn("stations: 3436 in the checked-in copy, 3301 regenerated", result.lines)
        result = compare(payload({"TEN": ["seaside"]}, schema=2), payload({"TEN": ["seaside"]}, schema=3))
        self.assertIn("schema: 2 in the checked-in copy, 3 regenerated", result.lines)

    def test_a_long_delta_is_counted_rather_than_listed(self) -> None:
        # The real transport facet moved 149 stations at once. One line per facet
        # is the report; a line naming 149 codes is a report nobody reads.
        added = sorted(f"X{number:02d}" for number in range(20))
        result = compare(
            payload({"TEN": ["transport"]}),
            payload({"TEN": ["transport"], **{code: ["transport"] for code in added}}),
        )
        self.assertEqual(result.moved, 1)
        self.assertIn(f"and {20 - CODES_SHOWN} more", result.lines[0])
        self.assertIn(f"X{CODES_SHOWN - 1:02d}", result.lines[0])
        self.assertNotIn(f"X{CODES_SHOWN:02d}", result.lines[0], "the line names the cap and no more")


class ReportTest(unittest.TestCase):
    def test_a_registry_change_with_no_station_behind_it_is_still_reported(self) -> None:
        # A source can ship and match no station yet. Nothing moved, and the
        # checked-in copy is still wrong, so the failure has to be counted in the
        # unit that is wrong. Reported as "0 facet(s) moved", a red run sends its
        # reader looking for the mistake in a file that has none.
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "destination-facets.json"
            recorded = payload({"TEN": ["seaside"]}, supported=["seaside"])
            regenerated = payload({"TEN": ["seaside"]}, supported=["seaside", "transport"])
            reference.write_text(json.dumps(recorded), encoding="utf-8")
            expected = len(compare(recorded, regenerated).lines)
            report = io.StringIO()
            with mock.patch.object(check_facet_reference, "build", return_value=regenerated):
                with contextlib.redirect_stdout(report):
                    code = check_facet_reference.check(Path("no-such-feed"), reference, set())
        self.assertEqual(code, 1)
        self.assertIn(f"{expected} difference(s) against the registry", report.getvalue())
        self.assertIn("tools/regenerate_destination_facets.py", report.getvalue())
        self.assertNotIn("0 facet(s) moved", report.getvalue())


class MissingReferenceTest(unittest.TestCase):
    def test_a_checkout_with_no_reference_data_fails_before_it_reads_a_feed(self) -> None:
        # The failure this guards is a confusing one: regenerating first and then
        # finding nothing to compare with costs minutes and reports nothing. The
        # feed here does not exist, so a run that reached it would fail differently.
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder) / "destination-facets.json"
            self.assertEqual(main(["--feed", "no-such-feed", "--reference", str(missing)]), 2)
