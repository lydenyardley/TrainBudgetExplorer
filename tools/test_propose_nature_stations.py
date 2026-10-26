"""Tests for the nature-site proposer.

The tool's job is to be *believed* about what it did not do, so most of these
are about refusals: it must not read a host it was not told about, must not
call a coach station a rail one, must not match a name that is only part of a
station's, and must never write to the reviewed list. Every fetch here is a
stub; the tests make no network request.
"""

from __future__ import annotations

import io
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from trainbudget.feeds.make_synthetic_feed import build_synthetic_feed
from tools import propose_nature_stations as proposer

FEED_STATIONS = {
    "ATB": "ATTENBOROUGH",
    "BCB": "BURSCOUGH BRIDGE",
    "BCJ": "BURSCOUGH JN",
    "HAY": "HAYES & HARLNGTN",
    "ZHX": "HATTON CROSS UND",
    "ZUX": "UXBRIDGE UND",
    "XDO": "BATH BUS STATION",
    "GBR": "LONDON BRIDGE",
}

PAGE = """
<html><body>
  <nav>Home Nature Reserves Donate</nav>
  <h1>Marton Mere</h1>
  <p>The nearest railway station is Burscough Bridge, about a mile away.</p>
  <p>Buses run from Preston Bus Station and from the Derby Bus Station.</p>
  <p>Cam and Dursley is the nearest train station for the Slimbridge reserve.</p>
  <p>The nearest station is Hatton Cross on the Piccadilly line.</p>
  <script>var station = 'Leeds';</script>
</body></html>
"""


class TextTest(unittest.TestCase):
    def test_script_bodies_are_not_evidence(self) -> None:
        text = proposer.page_text(PAGE)
        self.assertNotIn("Leeds", text)
        self.assertIn("Burscough Bridge", text)

    def test_a_paragraph_with_no_full_stop_still_yields_its_station(self) -> None:
        # The bug this guards: a 900-character block with no punctuation was one
        # "sentence", so the station in the last line was cut away.
        block = "Access " + ("the reserve is open all day " * 12) + "Brandon station is the way in"
        pieces = proposer.sentences(block)
        self.assertTrue(any("Brandon station" in piece for piece in pieces), pieces)

    def test_a_sentence_mentioning_a_train_is_kept(self) -> None:
        kept = proposer.station_sentences("The reserve is open. Trains run hourly. Closed Mondays.")
        self.assertEqual(kept, ["Trains run hourly."])

    def test_a_sentence_with_no_transport_word_is_dropped(self) -> None:
        self.assertEqual(proposer.station_sentences("The reserve is open all day."), [])


class LookupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.lookup = proposer.StationLookup(FEED_STATIONS)

    def test_a_whole_name_matches(self) -> None:
        self.assertEqual(self.lookup.match("Burscough Bridge"), "BCB")

    def test_a_station_the_feed_abbreviates_does_not_match_by_rule(self) -> None:
        # "Junction" against "BURSCOUGH JN": a human resolves this, not a rule.
        self.assertIsNone(self.lookup.match("Burscough Junction"))
        self.assertEqual(self.lookup.match("Burscough JN"), "BCJ")

    def test_a_qualifier_the_dtd_adds_is_matched(self) -> None:
        self.assertEqual(self.lookup.match("Hatton Cross"), "ZHX")

    def test_a_name_the_feed_truncates_is_not_matched(self) -> None:
        # "HAYES & HARLNGTN" cannot be matched by rule, and guessing at it would
        # be the false claim this tool exists not to make.
        self.assertIsNone(self.lookup.match("Hayes and Harlington"))

    def test_the_longest_reading_of_a_phrase_wins(self) -> None:
        found = self.lookup.matches("Burscough Bridge railway station")
        self.assertEqual(found, [("Burscough Bridge", "BCB")])

    def test_a_coach_station_is_not_a_destination(self) -> None:
        found = self.lookup.matches("Buses run from Preston Bus Station and Derby Bus Station")
        self.assertEqual(found, [])

    def test_a_rail_station_after_a_coach_mention_is_still_found(self) -> None:
        found = self.lookup.matches("Take the bus from Derby Bus Station, then walk to Attenborough station")
        self.assertEqual([crs for _, crs in found], ["ATB"])


class HostGuardTest(unittest.TestCase):
    def test_a_trust_needs_naming_before_it_is_read(self) -> None:
        # The network's own sites are read; a member trust's domain is not,
        # until the operator names it.
        self.assertFalse(proposer.host_allowed("https://www.essexwt.org.uk/nature-reserves/thorndon"))
        self.assertTrue(
            proposer.host_allowed("https://www.essexwt.org.uk/x", ("essexwt.org.uk",))
        )
        self.assertTrue(proposer.host_allowed("https://www.wildlifetrusts.org/nature-reserves"))

    def test_any_other_host_is_refused(self) -> None:
        self.assertFalse(proposer.host_allowed("https://example.com/nature"))
        self.assertFalse(proposer.host_allowed("https://wildlifetrusts.org.evil.example/x"))

    def test_a_host_that_merely_contains_an_allowed_name_is_refused(self) -> None:
        self.assertFalse(proposer.host_allowed("https://notwildlifetrusts.org/x"))

    def test_a_trusted_host_with_a_lookalike_suffix_is_refused(self) -> None:
        self.assertFalse(
            proposer.host_allowed("https://wwt.org.uk.evil.example/x", ("wwt.org.uk",))
        )

    def test_a_redirect_off_the_allowed_hosts_is_refused(self) -> None:
        # urllib follows a redirect on its own, so the allowlist has to be
        # enforced there too: a page on wildlifetrusts.org that answers with a
        # 302 to elsewhere must not be read from there.
        handler = proposer._AllowedHostRedirect(())
        with self.assertRaises(urllib.error.HTTPError) as refused:
            handler.redirect_request(
                urllib.request.Request("https://www.wildlifetrusts.org/x"),
                None,
                302,
                "Found",
                {},
                "https://example.com/nature",
            )
        refused.exception.close()

    def test_a_redirect_between_allowed_hosts_is_followed(self) -> None:
        handler = proposer._AllowedHostRedirect(("essexwt.org.uk",))
        request = handler.redirect_request(
            urllib.request.Request("https://www.wildlifetrusts.org/x"),
            None,
            302,
            "Found",
            {},
            "https://www.essexwt.org.uk/thorndon",
        )
        self.assertEqual(request.full_url, "https://www.essexwt.org.uk/thorndon")


class ProposeTest(unittest.TestCase):
    def _propose(self, html: str, url: str = "https://www.wildlifetrusts.org/nature-reserves/x"):
        with mock.patch.object(proposer, "fetch", return_value=(200, html)):
            return proposer.propose_for_url(url, FEED_STATIONS)

    def test_a_named_station_comes_with_its_evidence(self) -> None:
        found, _, error = self._propose(PAGE)
        self.assertIsNone(error)
        proposals = {p.crs: p for p in found}
        self.assertIn("BCB", proposals)
        self.assertIn("Burscough Bridge", proposals["BCB"].evidence)
        # "Hatton Cross" reaches a feed that calls it "HATTON CROSS UND".
        self.assertIn("ZHX", proposals)
        # "Derby Bus Station" names a coach station, not a destination.
        self.assertNotIn("XDO", proposals)

    def test_a_page_with_no_transport_mentions_proposes_nothing(self) -> None:
        found, _, _ = self._propose("<p>A meadow with orchids and a car park.</p>")
        self.assertEqual(found, [])

    def test_a_fragment_of_a_matched_name_is_not_called_unmatched(self) -> None:
        # "Hatton Cross" was found, so "Hatton" is not a station the feed is
        # missing; listing it sends a reviewer after a station already proposed.
        found, unmatched, _ = self._propose(PAGE)
        self.assertIn("ZHX", {p.crs for p in found})
        self.assertNotIn("Hatton", unmatched)

    def test_a_page_the_tool_could_not_read_is_reported(self) -> None:
        with mock.patch.object(proposer, "fetch", return_value=(403, "")):
            found, _, error = proposer.propose_for_url("https://www.wildlifetrusts.org/x", FEED_STATIONS)
        self.assertEqual(found, [])
        self.assertEqual(error, "HTTP 403")

    def test_an_unreadable_page_is_named_rather_than_skipped(self) -> None:
        # The station list comes from the synthetic feed and the page from a
        # stubbed fetch: the default --feed is the licensed download, which a
        # clean checkout does not have, and the live site is not under test.
        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(Path(tmp) / "fares")
            with mock.patch.object(proposer, "fetch", return_value=(404, "")), \
                    redirect_stderr(buffer), redirect_stdout(io.StringIO()):
                code = proposer.main(
                    ["--url", "https://www.wildlifetrusts.org/nature-reserves/x",
                     "--feed", str(feed)]
                )
        self.assertEqual(code, 0)
        self.assertIn("not read", buffer.getvalue())

    def test_a_page_from_an_unnamed_trust_is_refused_before_any_fetch(self) -> None:
        with mock.patch.object(proposer, "fetch") as fetch:
            stderr = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                code = proposer.main(["--url", "https://www.essexwt.org.uk/nature-reserves/thorndon"])
        self.assertEqual(code, 2)
        fetch.assert_not_called()
        self.assertIn("--allow-host", stderr.getvalue())

    def test_the_tool_writes_no_file_and_says_so(self) -> None:
        out = io.StringIO()
        with mock.patch.object(proposer, "fetch", return_value=(200, PAGE)), mock.patch.object(
            proposer, "load_stations", return_value=FaresStub()
        ):
            with redirect_stderr(io.StringIO()), redirect_stdout(out):
                code = proposer.main(["--url", "https://www.wildlifetrusts.org/nature-reserves/x"])
        self.assertEqual(code, 0)
        self.assertIn("nothing was written to any file", out.getvalue())


class FaresStub:
    """Just enough of a FaresDb for main()'s station-name lookup."""

    def __init__(self) -> None:
        self.locations_by_crs = {
            code: mock.Mock(name=name) for code, name in FEED_STATIONS.items()
        }
        for code, location in self.locations_by_crs.items():
            location.name = FEED_STATIONS[code]


class AlreadyListedTest(unittest.TestCase):
    def test_a_station_already_on_the_list_is_not_re_proposed(self) -> None:
        buffer = io.StringIO()
        with mock.patch.object(proposer, "fetch", return_value=(200, PAGE)), mock.patch.object(
            proposer, "load_stations", return_value=FaresStub()
        ):
            with redirect_stderr(io.StringIO()), redirect_stdout(buffer):
                proposer.main(["--url", "https://www.wildlifetrusts.org/nature-reserves/x"])
        self.assertIn("already listed", buffer.getvalue())
        self.assertNotIn("proposed BCB", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
