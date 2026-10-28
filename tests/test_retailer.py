"""Tests for the outbound ticket links.

Two properties matter more than the exact parameters: a tracked link must land
on the same search as an untracked one, and a link must never carry a journey
this tool invented.
"""

from __future__ import annotations

import unittest
from datetime import date
from urllib.parse import parse_qs, unquote, urlparse

from trainbudget.fares.retailer import (
    AFFILIATE_NETWORKS,
    DISCLOSURE,
    PROVIDERS,
    pairing_warning,
    provider_table,
    ticket_link,
)

WHEN = date(2026, 10, 4)


class TicketLinkTest(unittest.TestCase):
    def test_a_national_rail_link_carries_the_codes_and_the_date(self) -> None:
        link = ticket_link("GRN", "NOT", provider="national_rail", when=WHEN)
        query = parse_qs(urlparse(link.url).query)
        self.assertEqual(query["origin"], ["GRN"])
        self.assertEqual(query["destination"], ["NOT"])
        self.assertEqual(query["leavingDate"], ["20261004"])
        self.assertEqual(query["type"], ["single"])

    def test_a_trainline_link_carries_the_party_and_an_iso_date(self) -> None:
        link = ticket_link("GRN", "NOT", provider="trainline", when=WHEN, adults=2)
        query = parse_qs(urlparse(link.url).query)
        self.assertEqual(query["outwardDate"], ["2026-10-04"])
        self.assertEqual(query["passengers[]"], ["2"])

    def test_a_link_with_no_date_leaves_the_date_out(self) -> None:
        link = ticket_link("GRN", "NOT", when=None)
        self.assertNotIn("leavingDate", link.url)
        self.assertNotIn("date", link.url)
        self.assertIn("origin=GRN", link.url)

    def test_a_provider_is_never_sent_a_parameter_it_does_not_declare(self) -> None:
        # National Rail's page declares no party parameter, so an adults value
        # must not reach its URL.
        link = ticket_link("GRN", "NOT", provider="national_rail", adults=2)
        self.assertNotIn("passengers", link.url)
        self.assertNotIn("adults", link.url)

    def test_lowercase_codes_are_normalised(self) -> None:
        link = ticket_link("grn", "not")
        self.assertIn("origin=GRN", link.url)
        self.assertIn("destination=NOT", link.url)

    def test_no_journey_is_sent(self) -> None:
        # The fare is a walk-up fare valid on any train that day, so sending a
        # departure would pick a train on the reader's behalf.
        link = ticket_link("GRN", "NOT", when=WHEN)
        for token in ("departure", "arrival", "train", "service", "train_uid"):
            self.assertNotIn(token, link.url)

    # -- untracked by default --------------------------------------------

    def test_a_plain_link_is_untracked_and_carries_no_disclosure(self) -> None:
        link = ticket_link("GRN", "NOT")
        self.assertFalse(link.tracked)
        # noreferrer as well as noopener: the page's address holds the reader's
        # search, and the seller must not be told it by the click (audit item 9,
        # 28 October 2026).
        self.assertEqual(link.rel, "noopener noreferrer")
        self.assertIsNone(link.disclosure)
        self.assertTrue(link.url.startswith("https://www.nationalrail.co.uk/"))

    def test_a_network_without_an_advertiser_stays_untracked(self) -> None:
        link = ticket_link("GRN", "NOT", network="partnerize", advertiser_id=None)
        self.assertFalse(link.tracked)
        self.assertNotIn("prf.hn", link.url)

    # -- tracked links ----------------------------------------------------

    def test_a_tracked_link_lands_on_the_same_search(self) -> None:
        plain = ticket_link("GRN", "NOT", when=WHEN)
        tracked = ticket_link(
            "GRN",
            "NOT",
            when=WHEN,
            network="partnerize",
            advertiser_id="123456",
            publisher_id="789",
        )
        # The destination is escaped whole, so the wrapper carries no raw "?" or
        # "&" of its own: everything after the marker is the landing page.
        landing = unquote(tracked.url.split("destination:", 1)[1])
        self.assertEqual(landing, plain.url)

    def test_a_tracked_link_declares_itself_to_the_reader_and_the_crawler(self) -> None:
        tracked = ticket_link("GRN", "NOT", network="partnerize", advertiser_id="123456")
        self.assertTrue(tracked.tracked)
        self.assertIn("nofollow", tracked.rel)
        self.assertIn("sponsored", tracked.rel)
        self.assertIn("noreferrer", tracked.rel)
        self.assertEqual(tracked.disclosure, DISCLOSURE)

    def test_an_awin_link_uses_the_cread_form(self) -> None:
        tracked = ticket_link(
            "GRN", "NOT", network="awin", advertiser_id="2829", publisher_id="111"
        )
        self.assertTrue(tracked.url.startswith("https://www.awin1.com/cread.php?"))
        query = parse_qs(urlparse(tracked.url).query)
        self.assertEqual(query["awinmid"], ["2829"])
        self.assertEqual(query["awinaffid"], ["111"])
        self.assertTrue(query["ued"][0].startswith("https://www.nationalrail.co.uk/"))

    # -- refusals ---------------------------------------------------------

    def test_an_unknown_provider_is_refused(self) -> None:
        with self.assertRaises(KeyError) as caught:
            ticket_link("GRN", "NOT", provider="ferry")
        self.assertIn("national_rail", str(caught.exception))

    def test_an_unknown_network_is_refused(self) -> None:
        with self.assertRaises(KeyError):
            ticket_link("GRN", "NOT", network="nope", advertiser_id="1")

    def test_a_seller_linked_through_the_wrong_network_is_warned_about(self) -> None:
        warning = pairing_warning("trainline", "awin")
        self.assertIsNotNone(warning)
        self.assertIn("partnerize", warning)
        self.assertIsNone(pairing_warning("trainline", "partnerize"))
        self.assertIsNone(pairing_warning("trainline", None))
        # Where the seller's network is not known, nothing is claimed.
        self.assertIsNone(pairing_warning("national_rail", "awin"))

    def test_the_provider_table_matches_the_providers(self) -> None:
        table = provider_table()
        self.assertEqual({row[0] for row in table}, set(PROVIDERS))
        self.assertIn("origin", table[0][2])
        self.assertEqual(set(AFFILIATE_NETWORKS), {"awin", "partnerize"})

    # -- what a live check found ------------------------------------------

    def test_every_provider_carries_a_recorded_link_check(self) -> None:
        # A declared parameter is a claim about the page; a recorded check is a
        # claim about the link. Carrying both keeps them from being confused.
        for key, _label, _params, _note, verified in provider_table():
            self.assertTrue(verified, f"{key} carries no recorded link check")

    def test_neither_link_is_recorded_as_working(self) -> None:
        # ADR-0017 records the live check of 22 September 2026: the National Rail
        # link found no journeys, and Trainline refused an automated search. If
        # either is ever made to work, this test fails so the record has to be
        # corrected with it rather than quietly going stale.
        checks = {row[0]: row[4] for row in provider_table()}
        self.assertIn("no journeys", checks["national_rail"])
        self.assertIn("refused", checks["trainline"])

    # -- the fallback link ------------------------------------------------

    def test_a_fallback_link_is_the_sellers_own_search_page(self) -> None:
        # ADR-0017: the parameterised link is not known to land on a search, so
        # the alternative has to be a link that lands somewhere a reader can use.
        link = ticket_link("GRN", "NOT", provider="national_rail", when=WHEN, mode="fallback")
        self.assertEqual(link.url, PROVIDERS["national_rail"].fallback_url)
        self.assertNotIn("?", link.url)
        self.assertFalse(link.tracked)

    def test_a_fallback_link_carries_no_search_at_all(self) -> None:
        link = ticket_link("GRN", "NOT", when=WHEN, adults=2, mode="fallback")
        for token in ("origin", "destination", "date", "adults", "passengers"):
            self.assertNotIn(token, link.url)

    def test_a_fallback_link_is_still_trackable_and_lands_the_same(self) -> None:
        plain = ticket_link("GRN", "NOT", mode="fallback")
        tracked = ticket_link(
            "GRN", "NOT", mode="fallback", network="partnerize", advertiser_id="123456"
        )
        landing = unquote(tracked.url.split("destination:", 1)[1])
        self.assertEqual(landing, plain.url)
        self.assertIn("nofollow", tracked.rel)

    def test_an_unknown_link_mode_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            ticket_link("GRN", "NOT", mode="clever")


if __name__ == "__main__":
    unittest.main(verbosity=2)
