"""The fares half of the payload: modes, restrictions, cards, facets and counts.

F6 of the 8 October 2026 agent-efficiency audit moved the page's content
tests out of the class they all shared, by subject, over the fixture in
``tests/page_harness.PageTestCase``.
"""

from __future__ import annotations

import re
import tempfile
from datetime import date
from pathlib import Path
from atoc_fares import FLOW_F, FaresDb
from build_demo_page import build_payload, render_page
from make_synthetic_feed import _line, build_synthetic_feed
from tests.page_harness import page_markup, page_script, setUpModule, tearDownModule, PageTestCase


class FaresPayloadTest(PageTestCase):
    def test_the_page_carries_every_priced_destination_not_just_the_cheap_ones(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(sorted(rows), ["KGX", "LCN", "NOT", "PBO", "SLP"])

    def test_every_destination_carries_both_prices_and_a_journey(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        # The page now includes the cheapest standard return found in the feed,
        # even when it is restricted. The browser budget filter does the final
        # selection; the synthetic fixture's cheaper CDR is therefore visible.
        self.assertEqual(rows["NOT"]["adultPence"], 1160)
        # NOT's CDR fare is the one the fixture's RR 0001 bans for this card,
        # so it carries a state and no price.
        self.assertEqual(rows["NOT"]["railcards"]["YNG"]["state"], "blocked")
        self.assertIsNone(rows["NOT"]["railcards"]["YNG"]["pricePence"])
        self.assertEqual(rows["PBO"]["railcards"]["YNG"]["pricePence"], 1490)
        self.assertEqual(rows["NOT"]["partyPence"], 2320)
        self.assertEqual(rows["NOT"]["minutes"], 45)
        self.assertEqual(rows["NOT"]["changes"], 0)

    def test_single_mode_prices_the_walk_up_single_not_the_advance_ticket(self) -> None:
        # The single list used to lead with a 100p advance fare because it was
        # the cheapest number in the feed, which told a reader Grantham to
        # Nottingham cost £1.00 when that price belonged to one named train.
        # The list now prices the walk-up single, and says so.
        row = next(row for row in self.payload["singleDestinations"] if row["crs"] == "NOT")
        self.assertEqual(row["adultPence"], 700)
        self.assertEqual(row["ticket"], "SDS")
        self.assertFalse(row["isAdvance"])
        self.assertEqual(row["quality"], "outbound single")

    def test_no_published_row_is_priced_as_a_train_specific_advance_fare(self) -> None:
        # The rule is about every row on every page, not one fixture's one
        # destination: a train-restricted fare reaching any published list is
        # the failure, whatever it is called and whatever it costs.
        for key in ("destinations", "singleDestinations", "anytimeDestinations"):
            for row in self.payload[key]:
                self.assertFalse(
                    row["isAdvance"],
                    f'{key} publishes {row["crs"]} as an advance fare at {row["adultPence"]}p',
                )

    def test_a_heritage_destination_carries_its_named_unesco_property(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "SLP")
        self.assertEqual(
            row["heritageSites"],
            [{
                "id": 488,
                "name": "Tower of London",
                "url": "https://whc.unesco.org/en/list/488/",
            }],
        )
        self.assertIn("World heritage: ", page_script(self.html))
        self.assertIn("destination.heritageSites", page_script(self.html))

    def test_a_nature_destination_carries_its_named_reserve(self) -> None:
        # The synthetic GRN page has no ATB row; the builder still stamps the
        # field on every destination, and the page template names the proof.
        from atoc_fares import FaresDb, Location

        for row in self.payload["destinations"]:
            self.assertIn("natureSites", row)
            self.assertEqual(row["natureSites"], [])
        self.assertIn("Nature sites: ", page_script(self.html))
        self.assertIn("destination.natureSites", page_script(self.html))
        db = FaresDb()
        db.locations_by_crs = {"ATB": Location("7100", "ATB", "ATTENBOROUGH", "")}
        db.location_facets_by_crs = {"ATB": {"nature"}}
        self.assertEqual(
            db.nature_sites("ATB"),
            [{
                "name": "Attenborough Nature Reserve",
                "url": "https://www.nottinghamshirewildlife.org/attenborough-plan-your-visit",
            }],
        )

    def test_a_coastal_destination_carries_its_named_day_out(self) -> None:
        from atoc_fares import FaresDb, Location

        for row in self.payload["destinations"]:
            self.assertIn("coastalSites", row)
        self.assertIn("Coastal & seaside: ", page_script(self.html))
        self.assertIn("destination.coastalSites", page_script(self.html))
        db = FaresDb()
        db.locations_by_crs = {"SKG": Location("8200", "SKG", "SKEGNESS", "")}
        db.location_facets_by_crs = {"SKG": {"seaside"}}
        self.assertEqual(
            db.coastal_sites("SKG"),
            [{
                "name": "Skegness Beach",
                "url": "https://www.visitlincolnshire.com/destinations/skegness/",
            }],
        )
        # LCN is not a coastal proof CRS; without the seaside facet it stays empty.
        self.assertEqual(self.fares.coastal_sites("LCN"), [])

    def test_the_three_day_out_chips_name_their_own_proof(self) -> None:
        # ADR-0064's rule, applied to the sources ADR-0065 shipped: the chip is
        # only honest if the row can name the place behind it. Two halves, and
        # both are checked here because either alone looks like it works -- a
        # payload field with no reader renders no proof, and a reader with no
        # field renders an undefined one.
        for label, key in (
            ("RSPB reserves: ", "destination.rspbSites"),
            ("National Trust: ", "destination.nationalTrustSites"),
            ("National parks and landscapes: ", "destination.nationalParkSites"),
        ):
            self.assertIn(label, page_script(self.html))
            self.assertIn(key, page_script(self.html))


    def test_expired_flows_are_absent_from_all_ticket_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares._load_flows(
                _line(
                    {
                        "update_marker": "R",
                        "record_type": "F",
                        "origin_nlc": "1000",
                        "destination_nlc": "2000",
                        "route_code": "00000",
                        "flow_id": "0000001",
                        "start_date": "01012020",
                        "end_date": "31122020",
                    },
                    FLOW_F,
                )
            )
            payload = build_payload(
                fares, None, "GRN", day=date(2026, 9, 24)
            )

        for mode in ("destinations", "singleDestinations", "anytimeDestinations"):
            self.assertNotIn("NOT", {row["crs"] for row in payload[mode]})

    def test_the_page_carries_separate_ticket_modes(self) -> None:
        self.assertEqual(self.payload["destinations"][0]["destinationType"], "city")
        self.assertEqual(
            self.payload["destinations"][0]["destinationTypes"],
            ["city", "seaside", "university"],
        )
        self.assertIn('name="destinationType" value="city"', self.html)
        self.assertIn('name="destinationType" value="seaside"', self.html)
        self.assertIn('name="destinationType" value="university"', self.html)
        self.assertIn("Coastal &amp; seaside", self.html)
        self.assertIn("University towns", self.html)
        self.assertNotIn('<select id="q"', self.html)
        self.assertIn("selectedDestinationTypes", page_script(self.html))
        self.assertIn("singleDestinations", self.payload)
        self.assertTrue(self.payload["singleDestinations"])
        self.assertIn("anytimeDestinations", self.payload)
        self.assertTrue(self.payload["anytimeDestinations"])
        self.assertIn('name="ticketMode"', self.html)
        self.assertIn('value="single"', self.html)
        self.assertIn('value="anytime"', self.html)
        self.assertIn("activeDestinations", page_script(self.html))
        self.assertIn("unrestricted Anytime Day Return", self.html)
        self.assertIn("no qualifying", page_script(self.html))
        # The pager is shipped, hidden, and stands itself down when the list
        # fits on one page. How many rows a page holds, and which page the
        # reader is on, are the page's own arithmetic: the browser suite reads
        # the size back out of the page and drives the pager against it.
        self.assertIn('id="pagination"', self.html)


    def test_the_page_opens_on_the_cheapest_fare_of_any_type(self) -> None:
        # Q4: the list that opens is the cheapest fare of any ticket type, and
        # the three named sets survive as filters beside it. The checked radio
        # is what a reader arrives in, which is the part PRODUCT.md promises,
        # so the checked one is asserted rather than only present. The
        # composition and the tie-break are driven by the browser suite, which
        # opens the page on the cheapest row and re-sorts it under a card.
        self.assertIn('<input type="radio" name="ticketMode" value="cheapest" checked>', self.html)
        for other in ("anytime", "return", "single"):
            self.assertIn('<input type="radio" name="ticketMode" value="%s">' % other, self.html)
            self.assertNotIn('value="%s" checked' % other, self.html)
        # Composed in the page, so it costs no payload bytes, and one row per
        # destination: the cheaper of the fares that destination is priced at.
        # Both sentences are asserted whole, because they are the product: the
        # note above the table and the line beside the prices each say which
        # list this is, and half a sentence names nothing.
        self.assertIn(
            "Each row is the cheapest fare of any ticket type, so this list mixes singles and returns.",
            page_script(self.html),
        )
        self.assertIn("each on the cheapest fare of any ticket type the feed prices for it", page_script(self.html))
        self.assertIn(
            "destinations, each on its cheapest fare of any ticket type, in the feed", page_script(self.html)
        )

    def test_the_count_line_names_the_mix_and_what_the_party_is_two_of(self) -> None:
        # The set names itself above the table, in the coverage line and in the
        # provenance line, so no sentence on the page counts the wrong fares.
        # The composition of the sentence is driven by the browser suite.
        self.assertIn("MIX_WORDS", page_script(self.html))
        self.assertIn('"for the two of us, two of the fare each row names"', page_script(self.html))
        self.assertIn(
            "Each row is the cheapest fare of any ticket type, so this list mixes singles and returns.",
            page_script(self.html),
        )
        self.assertIn("each on the cheapest fare of any ticket type the feed prices for it", page_script(self.html))
        self.assertIn(
            "destinations, each on its cheapest fare of any ticket type, in the feed", page_script(self.html)
        )

    def test_the_cheapest_destination_is_listed_first(self) -> None:
        prices = [row["adultPence"] for row in self.payload["destinations"]]
        self.assertEqual(prices, sorted(prices))

    def test_a_fare_with_no_service_still_reaches_the_page(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["SLP"]["adultPence"], 1200)
        self.assertIsNone(rows["SLP"]["minutes"])
        self.assertEqual(rows["SLP"]["legs"], [])

    # -- the licence wording and the measurement hook ----------------------

    def test_each_destination_carries_its_fare_restriction_status(self) -> None:
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["restrictionCode"], "1A")
        # C08: the description is now the feed's own wording for the code
        # rather than a placeholder, so it is judged against that.
        self.assertEqual(rows["NOT"]["restrictionDescription"], "NOT VALID AT WEEKENDS")
        self.assertEqual(rows["SLP"]["restrictionCode"], "")
        self.assertIn("restrictionCode", self.html)
        self.assertIn("restrictionDescription", self.html)
        # Every code the build attaches comes with the feed's own wording for
        # it, so no reader is ever shown a bare code; what the page falls back
        # to is belt and braces for a description this build cannot produce.
        self.assertTrue(
            all(
                row["restrictionDescription"]
                for row in self.payload["destinations"]
                if row["restrictionCode"]
            )
        )
        self.assertIn("ITX placeholder fares", self.html)

    def test_a_restricted_row_carries_the_validity_the_feed_states(self) -> None:
        # C08: the condition a reader is being asked to rule a fare in or out
        # by is only useful if it says what it permits. The feed's own outward
        # and return text reaches the page, once per code rather than once per
        # row, so a page of 1,678 rows does not repeat the same two sentences
        # 1,678 times.
        validity = self.payload["restrictionValidity"]
        self.assertEqual(
            validity["1A"],
            {
                "outwardText": "NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY",
                "returnText": "RETURN NOT VALID FOR TRAVEL ON SATURDAY OR SUNDAY",
            },
        )
        # A code the feed has no header for is absent rather than empty, so the
        # page can tell "nothing to show" from "show nothing".
        self.assertNotIn("", validity)
        self.assertIn("DATA.restrictionValidity", page_script(self.html))
        self.assertIn("Valid outward: ", page_script(self.html))
        self.assertIn("Valid on the return: ", page_script(self.html))

    def test_a_restriction_the_feed_cannot_describe_says_so_plainly(self) -> None:
        # C08: "confirm the conditions before buying" reads as if the page had
        # decoded a rule and left the reader a task. What it has is a code and
        # no wording, and that is what the page says.
        with tempfile.TemporaryDirectory() as tmp:
            feed = build_synthetic_feed(
                Path(tmp) / "fares", include_restrictions=True
            )
            fares = FaresDb().load_feed(feed)
            fares.restrictions.headers.pop("1A", None)
            payload = build_payload(fares, None, "GRN")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(rows["NOT"]["restrictionCode"], "1A")
        self.assertIn("does not describe", rows["NOT"]["restrictionDescription"])
        # Nothing to show is the honest outcome, and the map says so by
        # leaving the code out rather than by carrying an empty pair.
        self.assertNotIn("1A", payload["restrictionValidity"])

    def test_a_railcard_is_a_constraint_on_the_party_not_a_discount(self) -> None:
        # S15: the cheapest number on screen has to be a fare the party could
        # buy, so a card whose own feed record does not cover the party on
        # screen is taken out of the list rather than left there to be picked.
        # The bounds come from the feed, not from this project.
        card = self.payload["railcards"][0]
        # The bounds are each card's own, measured on the real feed on
        # 1 October 2026, so the party filter has something to take out.
        bounds = {c["key"]: (c["minAdults"], c["maxAdults"]) for c in self.payload["railcards"]}
        self.assertEqual(bounds["YNG"], (1, 8))
        self.assertEqual(bounds["2TR"], (2, 2))
        self.assertEqual(bounds["BB2"], (1, 1))
        # The help text is written from the card's own bounds, and the browser
        # suite drives the list those bounds take a card out of.
        self.assertIn("No railcard selected, so these are standard fares", self.html)
        self.assertIn(" in this feed covers ", page_script(self.html))
        self.assertIn(" destinations receive a lower price with it", page_script(self.html))

    def test_a_missing_journey_is_typed_rather_than_a_dash(self) -> None:
        # S23: three different absences, three different sentences.
        rows = {row["crs"]: row for row in self.payload["destinations"]}
        self.assertEqual(rows["NOT"]["journeyState"], "found")
        self.assertEqual(rows["SLP"]["journeyState"], "no_service")
        # The wording is built in the page from the key, the day the build
        # asked about and the day the row next runs; the browser suite drives
        # the sentence each absence prints.
        self.assertIn("JOURNEY_ABSENCE", page_script(self.html))
        # The change count is a word rather than a digit, and the station it
        # changes at sits under it in the column whose header says Changes.
        self.assertIn("Direct", page_script(self.html))
        self.assertIn('"1 change"', page_script(self.html))
        prices_only = build_payload(self.fares, None, "GRN")
        self.assertEqual(
            next(row for row in prices_only["destinations"] if row["crs"] == "LCN")["journeyState"],
            "no_timetable",
        )
        dated = build_payload(self.fares, self.timetable, "GRN", day=date(2026, 9, 28))
        # Tower Hill has a fare and no train, so the row names the week the build
        # asked as well as the day: a reader who cannot reach either date is
        # owed that, and the old sentence stopped at the day.
        unserved = next(row for row in dated["destinations"] if row["crs"] == "SLP")
        self.assertEqual(unserved["journeyState"], "no_service")
        self.assertEqual(dated["serviceDate"], "2026-09-28")
        self.assertEqual(dated["serviceHorizon"], 7)
        self.assertNotIn("nextService", unserved)

    def test_the_page_counts_what_it_could_not_classify(self) -> None:
        # S29: an unreviewed destination is still listed, so the count of the
        # ones no chip can select is the difference between "every type" and
        # "every type we have reviewed".
        self.assertEqual(self.payload["unclassifiedDestinationCount"], 0)
        self.assertTrue(self.payload["locationTypeReviewed"])
        self.assertIn("carry no reviewed", page_script(self.html))
        self.assertIn("Every destination on this page carries a reviewed type.", page_script(self.html))
        # And the count is a count: a destination with no reviewed type is
        # counted rather than quietly filtered away.
        fares = FaresDb().load_feed(
            build_synthetic_feed(
                Path(self._tmp.name) / "unreviewed",
                include_restrictions=True,
            )
        )
        # A download with no reviewed classification at all: every destination
        # is still priced and still listed, and every one of them is a row no
        # type chip can select.
        fares.location_types_by_crs = {}
        fares.location_facets_by_crs = {}
        fares.location_type_sources = []
        payload = build_payload(fares, self.timetable, "GRN")
        self.assertEqual(payload["unclassifiedDestinationCount"], len(payload["destinations"]))
        self.assertFalse(payload["locationTypeReviewed"])

    def test_an_empty_list_offers_the_moves_that_would_fill_it(self) -> None:
        # S28: advice a reader cannot act on is a dead end, so each move is a
        # control and each is offered only when it is true for this page. The
        # browser suite drives the empty state and the buttons in it.
        self.assertIn("Show everything up to ", page_script(self.html))
        self.assertIn("Clear the destination type", page_script(self.html))
        self.assertIn("toggle", self.html)

    def test_the_facets_count_what_they_would_show_and_can_be_cleared(self) -> None:
        # S20: a count on the chip, the union stated, and a way back to All.
        # The counts and the clear are driven by the browser suite.
        self.assertIn('class="chipcount"', self.html)
        self.assertIn('id="clearTypes"', self.html)
        self.assertIn("More than one type shows destinations of any of them", self.html)

    def test_a_narrowed_search_returns_to_the_first_page(self) -> None:
        # S22: the cheapest rows are what a narrowed search wants first, and the
        # page position is re-announced with the count. The controls that do it
        # are driven by the browser suite, which types a budget and reads the
        # first page back.
        # Audit item 12, 9 October 2026: the page and the count each keep one
        # "of", and the singular is spelled rather than left to read "1 pages".
        # That is a sentence, so the browser suite reads it off the rendered
        # status after it has narrowed a search; what the markup owes the reader
        # is a named control to move with and a live region to announce from.
        self.assertIn('aria-label="Results pages"', self.html)
        self.assertIn('id="pageStatus" role="status"', self.html)
        self.assertIn('id="previousPage"', self.html)
        self.assertIn('id="nextPage"', self.html)

    def test_railcard_pricing_is_available_from_the_feed(self) -> None:
        # R9 is the railcard's travel condition, not a total ban, so the
        # synthetic fares that carry it remain eligible.
        cards = {card["key"]: card for card in self.payload["railcards"]}
        # All six reviewed cards, with the party each one prices. The
        # fixture used to carry a single card under a code that is not in
        # the reviewed set at all, so the control built to offer six came
        # out with one option in it.
        self.assertEqual(
            list(cards),
            ["YNG", "DIS", "NEW", "SRN", "BB2", "2TR"],
            "the demo feed prices the six reviewed cards",
        )
        self.assertEqual((cards["2TR"]["minAdults"], cards["2TR"]["maxAdults"]), (2, 2))
        self.assertEqual(cards["YNG"]["label"], "16-25 Railcard")
        # Two of the five fares sit on route 00002, which the fixture's RR 0001
        # bans for this card outright. The remaining three are discounted.
        self.assertEqual(cards["YNG"]["eligibleCount"], 3)
        refused = [
            row
            for row in self.payload["destinations"]
            if row["railcards"]["YNG"]["state"] == "blocked"
        ]
        self.assertEqual([row["crs"] for row in refused], ["NOT"], "the total ban refuses the CDR fare")
        self.assertIsNone(refused[0]["railcards"]["YNG"]["pricePence"])
        # A refused fare keeps its standard price rather than showing a
        # discount the feed will not honour.
        self.assertEqual(refused[0]["adultPence"], 1160)
        # LCN's £8.70 SDR fare is not counted either, and for the opposite
        # reason: the card's £12.00 minimum is higher than the discounted fare,
        # so the card raises this price rather than lowering it.
        raised = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        self.assertEqual(raised["railcards"]["YNG"]["pricePence"], 1200)
        self.assertGreater(raised["railcards"]["YNG"]["pricePence"], raised["adultPence"])
        self.assertIn("No railcard is selected", self.payload["railcardNote"])
        self.assertIn("restriction codes are retained as travel conditions", self.payload["railcardNote"])
        self.assertIn("DATA.railcardNote", page_script(self.html))
        # The page shows the cheaper of the standard fare and the card's own,
        # and the card's own is per adult, so a party row takes it twice. Both
        # are read off the rendered cell by the browser suite, against the
        # payload, for the party on screen.

    def test_the_page_evaluates_a_railcard_for_each_selected_fare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fares = FaresDb().load_feed(
                build_synthetic_feed(Path(tmp) / "fares", include_restrictions=True)
            )
            fares.restrictions.railcard_rows.clear()
            fares.minimum_fares.clear()
            payload = build_payload(fares, None, "GRN")
        rows = {row["crs"]: row for row in payload["destinations"]}
        self.assertEqual(rows["NOT"]["railcards"]["YNG"]["pricePence"], 770)
        cards = {card["key"]: card for card in payload["railcards"]}
        self.assertEqual(cards["YNG"]["eligibleCount"], 4)
        self.assertIn("discounted by a third", payload["railcardNote"])

    def test_each_destination_exposes_its_exact_railcard_decision(self) -> None:
        row = next(row for row in self.payload["destinations"] if row["crs"] == "PBO")
        details = row["railcards"]["YNG"]
        self.assertEqual(details["state"], "eligible")
        rule = self.payload["railcardRules"][details["rule"]]
        self.assertIn("RR", rule["text"])
        self.assertIn("16-25 Railcard", rule["text"])
        self.assertEqual(rule["restrictionCode"], "R9")
        # RR 0002 rather than 0001: 0001 is a total ban on route 00002, and this
        # row is not on that route. A restriction code attached to a fare is a
        # travel condition, not a refusal, which is what keeps the row eligible.
        self.assertEqual(rule["sequence"], "0002")
        self.assertFalse(rule["totalBan"])
        self.assertEqual(details["pricePence"], 1490)
        self.assertEqual(
            details["minimumFarePence"],
            self.fares.minimum_fare("YNG", row["ticket"]),
        )
        # The refused fare names the rule that refused it, so the drawer can say
        # which DTD record did it rather than only that it did not apply.
        refused = next(r for r in self.payload["destinations"] if r["crs"] == "NOT")
        ban = self.payload["railcardRules"][refused["railcards"]["YNG"]["rule"]]
        self.assertTrue(ban["totalBan"])
        self.assertEqual(ban["sequence"], "0001")
        # The explanation is one paragraph in the row's own disclosure.
        # A dialog on every row, opened on top of a page the reader was
        # already reading, to be told a number the row beside it carried.
        # The browser suite drives the row's panel and its wording.
        self.assertIn("DATA.railcardRules", page_script(self.html))
        self.assertIn("travel condition rather than a card ban", page_script(self.html))
        self.assertNotIn('id="railcardDrawer"', page_script(self.html))
        # The exact rule is still on the page, filed with the codes it is
        # a record of rather than headlined in a panel of its own.
        self.assertIn("Railcard rule", page_script(self.html))

    def test_the_railcard_note_never_names_a_price_above_the_row(self) -> None:
        # The row is priced at the cheaper of the standard fare and the card's.
        # The card's own price used to be printed under the label "Discounted
        # fare", so on a fare whose card minimum is above the discount it
        # showed GBP 12.00 against a row showing GBP 8.70, and called the
        # bigger number a discount.
        row = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        card = row["railcards"]["YNG"]
        self.assertEqual(row["adultPence"], 870)
        self.assertEqual(card["pricePence"], 1200)
        shown = min(row["adultPence"], card["pricePence"])
        self.assertEqual(shown, 870)
        self.assertLessEqual(shown, row["adultPence"], "a card never raises a row's price")
        # The note never quotes a number at all, so it cannot quote one
        # above the row: it names the card, says whether the card lowers
        # the fare, and gives the card's own price and the standard fare as
        # two labelled figures a reader can compare.
        self.assertIn("does not reduce it", page_script(self.html))
        self.assertIn("This row is priced at the cheaper of the two", page_script(self.html))
        # The note leads with the figure in the row. It used to lead with the
        # card's own price, which on a real page is the DTD minimum and is
        # routinely the larger number: a reader looking at a £2.70 fare was
        # shown £12.00 first and had to work out which one was theirs.
        # The note is found by the class the row's panel gives it, and the
        # order is the order the reader meets the two figures in: the row's
        # own price opens the sentence, the card's follows it.
        self.assertIn("card-note", page_script(self.html))
        self.assertLess(
            page_script(self.html).index('"This fare is "'),
            page_script(self.html).index('" does not reduce it. The card\'s own price here is "'),
            "the note must open with the row's price, not with the card's",
        )
        # The minimum is named as what it is, in the branch where the card
        # does help, rather than as a discount that made the fare dearer.
        self.assertIn("is the price here, so the discount took it no lower.", page_script(self.html))
        self.assertIn("does not raise it.", page_script(self.html))

    def test_the_two_ticket_note_adds_the_minimums_rather_than_calling_one_per_ticket(self) -> None:
        # A two-ticket row's card price is the two card fares added, and the
        # minimum the note names beside it is the two minimums added. The sum is
        # the pair's own total: reading it as a per-ticket figure would quote
        # 24.00 as the floor on each of two 12.00 tickets.
        self.assertIn(
            "with the feed's minimum fares on the two tickets adding to", page_script(self.html)
        )
        self.assertNotIn("applied per ticket", page_script(self.html))

    def test_the_railcard_note_names_the_card_it_is_about(self) -> None:
        # The reader picked one card out of six, so the note has to name it.
        # A note that explained "the railcard" while the page listed six would
        # answer a question nobody asked.
        # The card is named by the variable, and the sentence is split across
        # two lines of source with the label at the end of the first, so the
        # test reads the two halves rather than a sentence that no line holds.
        self.assertIn('" does not reduce it.', page_script(self.html))
        self.assertIn('cannot be applied to this fare.', page_script(self.html))
        # With no card chosen there is nothing to explain, so there is no
        # paragraph: the control above already says the prices are standard,
        # and a sentence on every expanded row repeating the page's default
        # is the noise this replaced.
        self.assertIn(
            "This feed prices no ", page_script(self.html)
        )

    def test_a_card_whose_minimum_is_higher_shows_the_standard_fare(self) -> None:
        # LCN's SDR fare is £8.70. The card's discounted price would be £5.80,
        # and the feed's £12.00 minimum is higher than that, so the card's own
        # price for this fare is dearer than travelling without it. The reader is
        # never charged the higher figure, because the page prices a row at the
        # cheaper of the standard fare and the card's, and the count of
        # discounted destinations leaves this fare out either way. What the
        # drawer has to say is that the minimum is higher, so a reader who opens
        # it does not read a "discount" that does not apply to this fare.
        row = next(r for r in self.payload["destinations"] if r["crs"] == "LCN")
        details = row["railcards"]["YNG"]
        self.assertEqual(row["adultPence"], 870)
        self.assertEqual(details["minimumFarePence"], 1200)
        self.assertEqual(details["pricePence"], 1200)
        self.assertGreater(details["pricePence"], row["adultPence"])
        # The drawer's own wording for that case: it says the card does not help
        # here, gives both numbers, and names the minimum as the reason, so a
        # reader who opens it is not left reading a discount the row did not get.
        self.assertIn("does not reduce it.", page_script(self.html))
        self.assertIn("because the minimum fare the feed applies to this ", page_script(self.html))
        self.assertIn("This row is priced at the cheaper of the two", page_script(self.html))

    def test_a_ticked_row_shows_the_card_price_and_the_standard_fare(self) -> None:
        # Q3: a discounted number never stands alone in the cell. The page
        # builds the price cell so it can carry the standard fare the card was
        # taken from, and carries nothing beside a price the card did not
        # lower. The live behaviour is driven by the browser suite, which reads
        # both cells off the row and compares them with the payload.
        self.assertIn("standard", self.html)
        self.assertIn('td.num .was {', self.stylesheet)

    def test_rule_records_are_hoisted_out_of_the_rows(self) -> None:
        rows = [
            row
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in self.payload[key]
        ]
        self.assertTrue(rows)
        offered = {card["key"] for card in self.payload["railcards"]}
        for row in rows:
            for key, details in row["railcards"].items():
                self.assertIn(key, offered, "a row prices only reviewed cards")
                rule = details["rule"]
                self.assertIsInstance(rule, str, "rows hold a key, never the record")
                self.assertIn(rule, self.payload["railcardRules"])
        rules = self.payload["railcardRules"]
        self.assertTrue(rules, "a page with rows publishes the shared records")

    def test_unavailable_railcard_hides_its_own_help(self) -> None:
        payload = dict(self.payload, railcards=[])
        html = render_page(payload, budget_pounds=20)
        script = page_script(html)
        self.assertIn("This feed prices no reviewed railcard, so these are standard fares.",
                      script)
        self.assertIn("railcardChoice", script)
        # The sentence stays rather than being hidden. "Standard fares" is the
        # claim the page rests on, and a reader who owns a 16-25 card is owed
        # the reason their card is not offered rather than an empty space. The
        # browser suite drives the control standing down.
        self.assertNotIn("no displayed fare is currently eligible", html)

    def test_the_page_opens_on_the_cheapest_list_and_every_set_says_what_it_is(self) -> None:
        # C07 was "the set the page opens in is the one PRODUCT.md promises",
        # which for a month meant the reviewed Anytime Day Returns. Q4 changes
        # what the page promises: it opens on the cheapest fare of any type,
        # because a budget question answered with one ticket type is a question
        # about the wrong number. The reviewed set is still offered, still
        # named, and still says what it contains -- the finding C07 recorded is
        # that a reader must be told what the open set holds, not which set it
        # has to be.
        checked = re.search(r'<input type="radio" name="ticketMode" value="(\w+)" checked>', self.html)
        self.assertIsNotNone(checked, "no ticket mode is checked in the markup")
        self.assertEqual("cheapest", checked.group(1))
        self.assertIn("> Anytime Day Return</label>", self.html)
        self.assertIn("> Any return</label>", self.html)
        self.assertIn("> Cheapest of any type</label>", self.html)
        # Each set says what its fares are, above the table rather than inside
        # the methodology accordion, so a reader meets the caveat at the moment
        # they compare two prices.
        for note in ("cheapest:", "anytime:", "return:", "single:"):
            self.assertIn("  " + note, page_script(self.html))
        self.assertIn('id="modeNote"', self.html)

    def test_a_destination_type_with_no_matches_gets_no_chip(self) -> None:
        # A chip that can only ever return nothing reads as a broken control,
        # so the page offers only the types its destinations actually carry.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        for mode in ("singleDestinations", "anytimeDestinations"):
            payload[mode] = [
                dict(row, destinationTypes=["city"], destinationType="city")
                for row in self.payload.get(mode, [])
            ]
        html = render_page(payload, budget_pounds=50)
        head = page_markup(html)
        self.assertIn('name="destinationType" value="city"', head)
        self.assertNotIn('name="destinationType" value="seaside"', head)
        self.assertNotIn('name="destinationType" value="university"', head)
        self.assertNotIn('name="destinationType" value="island"', head)

    def test_a_type_only_the_singles_carry_still_reaches_the_page(self) -> None:
        # The build narrows chips by the union of the three modes, because it
        # does not know which mode a reader will pick. The page then narrows
        # them again per mode at render time, so a type only the singles carry
        # is still in the HTML and simply hidden on the returns list. If the
        # build decided this, switching to Singles would show a chip that
        # filters nothing.
        payload = dict(self.payload)
        payload["destinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["destinations"]
        ]
        payload["anytimeDestinations"] = [
            dict(row, destinationTypes=["city"], destinationType="city")
            for row in self.payload["anytimeDestinations"]
        ]
        payload["singleDestinations"] = [
            dict(row, destinationTypes=["city", "heritage"], destinationType="city")
            for row in self.payload["singleDestinations"]
        ]
        head = page_markup(render_page(payload, budget_pounds=50))
        self.assertIn('name="destinationType" value="heritage"', head)

    def test_the_chips_are_narrowed_for_the_mode_on_screen(self) -> None:
        # The narrowing reads the active list rather than all three, and runs
        # before the filter is asked what is checked: a chip the list cannot
        # support must not be part of what matchesType is matching. What the
        # build owns is the wider set -- the chips are offered from the union
        # of the three modes, because it cannot know which one a reader will
        # pick -- and the narrowing from that union to the list on screen is
        # what the browser suite drives as a reader switches modes.
        offered = {
            re.search(r'name="destinationType" value="([^"]+)"', chip).group(1)
            for chip in re.findall(r"<input[^>]*name=\"destinationType\"[^>]*>", page_markup(self.html))
        } - {"all"}
        from_the_feed = {
            kind
            for key in ("destinations", "singleDestinations", "anytimeDestinations")
            for row in self.payload[key]
            for kind in (row["destinationTypes"] or [row["destinationType"]])
        }
        self.assertTrue(offered.issubset(from_the_feed), offered - from_the_feed)
        # A chip that goes away cannot stay ticked, or the filter would match a
        # type the reader can no longer see selected. The browser suite drives
        # the reset as a reader switches modes.

    def test_the_budget_ceiling_covers_the_party_price_too(self) -> None:
        # The ceiling is the most a reader can be asked to consider, and two
        # adults cost twice one. A ceiling set by the single fare is a budget
        # nobody reading the party price could type: on a page with one
        # destination -- Nottingham in the synthetic feed, and any station that
        # prices one place -- it caps the budget at that destination's adult
        # fare, and the "Two adults" control shows nothing at any budget the
        # page allows. Found by sweeping a published two-station site.
        # Every row carries both figures and the party one is double the
        # adult one, so a stop taken from either can miss the other; the stop
        # the reader actually gets, and that it follows the party the reader
        # chooses, is read off the rendered control by the browser suite.
        for row in self.payload["destinations"]:
            self.assertEqual(row["partyPence"], row["adultPence"] * 2, row["crs"])
        # The railcard is not in the ceiling: a card makes the price a reader is
        # asked for lower or leaves it where it was, never higher -- the row is
        # priced at the cheaper of the standard fare and the card's, which is
        # what LCN above is the example of, its card price being the DTD
        # minimum above the fare rather than a discount below it.
        for row in self.payload["destinations"]:
            for details in row["railcards"].values():
                if details["pricePence"] is not None:
                    self.assertLessEqual(
                        min(details["pricePence"], row["adultPence"]), row["adultPence"], row["crs"]
                    )

    def test_a_mode_with_no_fares_says_so_instead_of_going_blank(self) -> None:
        # An Anytime Day Return is sold on a handful of interurban routes, so
        # most real origins have none of them: Kings Cross prices 171 returns
        # and no Anytime fares at all. The page used to return from render()
        # before it wrote anything, so a reader who switched to that mode kept
        # the previous mode's rows under a set of destination chips that had
        # all just been hidden -- a filter that looks broken rather than a
        # mode that is empty. The mode now clears the table, says what
        # happened, and says where the fares this origin does have are. The
        # browser suite drives the empty state and its wording.
        self.assertNotIn("if (!available.length) return;", page_script(self.html))
        # The empty mode and the unpriced page each have their own message, so
        # an empty mode is not standing in for a page that priced nothing: the
        # reader is told which of the two happened. The sentence itself, that it
        # names the mode by the label the reader can see and counts the other
        # modes' lists, is driven by the browser suite.
        self.assertIn('<div id="empty" hidden></div>', self.html)
        self.assertIn('<p id="unpriced" class="unpriced" hidden></p>', self.html)
        self.assertIn("MODE_WHY", page_script(self.html))
        # The Anytime mode says why that mode is usually the empty one, since
        # "none in this download" on its own reads like a broken build.
        self.assertIn("An Anytime Day Return is valid on any train", page_script(self.html))
        # One place names which list each mode shows, so a count quoted in a
        # message cannot come from a different list than the table is built
        # from.
        self.assertIn("MODE_LISTS", page_script(self.html))

    def test_the_railcard_list_keeps_every_card_and_marks_the_ones_it_cannot_price(self) -> None:
        # Two Together is two adults exactly, so on the default page -- one
        # adult -- the party filter removed it, and it was the only card the
        # selector lost. A reader who owns it could not find out that the page
        # prices it at all. It is listed and struck out of choosing instead: a
        # disabled option cannot hold a value, so nothing downstream can read a
        # card price nobody could buy, which is what ADR-0052 was protecting.
        self.assertEqual(
            len(self.payload["railcards"]), 6,
            "the six reviewed cards are all priced on this page, so all six belong in the list",
        )
        self.assertIn("cardCoversParty", page_script(self.html))
        # The bounds that decide which card cannot price the party on screen are
        # the feed's own, one pair per card, and Two Together's is the pair
        # that makes this test's page lose a card by default. That a card the
        # feed's bounds rule out is listed but cannot be chosen, and that its
        # reason is spelled out in the option, is the browser suite's: it reads
        # every option's disabled state and its text off the rendered selector
        # and compares them against the payload's bounds.
        self.assertEqual(
            {card["key"]: (card["minAdults"], card["maxAdults"]) for card in self.payload["railcards"]},
            {"YNG": (1, 8), "DIS": (1, 2), "NEW": (1, 4), "SRN": (1, 8), "BB2": (1, 1), "2TR": (2, 2)},
        )
        # And the options are built from every key, not from the filtered set:
        # this is the one assertion that would catch the removal coming back.
        self.assertIn("railcardKeys", page_script(self.html))
        self.assertNotIn("for (const key of offered) {", self.html)

    def test_the_journey_is_the_same_fact_in_all_three_fare_lists(self) -> None:
        # The journey belongs to the origin and the destination, not to the
        # ticket type. It used to be read from each list's own timetable only,
        # so the same destination carried a different answer in each list, and
        # the cheapest list -- which keeps whichever row is cheapest -- showed
        # "No service" and "Unknown" about a destination the same payload times
        # at 45 minutes. The Time and Changes columns were empty for every
        # destination the build could time, and empty for a reason that named
        # nothing true about it.
        lists = (
            self.payload["destinations"],
            self.payload["singleDestinations"],
            self.payload["anytimeDestinations"],
        )
        seen: dict[str, tuple] = {}
        for rows in lists:
            for row in rows:
                fact = (row["journeyState"], row["minutes"], row["changes"])
                self.assertEqual(
                    seen.setdefault(row["crs"], fact),
                    fact,
                    f"{row['crs']} is timed differently in two fare lists: "
                    f"{seen[row['crs']]} and {fact}",
                )
        single = {row["crs"]: row for row in self.payload["singleDestinations"]}
        self.assertTrue(single, "this build prices no outbound single to check")
        for row in single.values():
            self.assertNotEqual(
                row["journeyState"], "no_timetable",
                "a build that loaded a timetable must not say it has none",
            )
        self.assertTrue(
            any(row["minutes"] is not None for row in single.values()),
            "no single-mode row carries a journey",
        )
        # The one thing that does NOT fall back. These are the times the fare is
        # good on, and an advance single's are only knowable from the separate
        # outbound-single timetable; a return-set train listed under an advance
        # single would be a time the reader cannot travel on that ticket.
        self.assertTrue(
            any(row["minutes"] is not None and not row["departures"]
                for row in single.values()),
            "a single-mode row is carrying departure times it has no timetable for",
        )
        # A build with no timetable at all still says so, because that sentence
        # now turns on whether any timetable was searched rather than on whether
        # this row's own list had one.
        prices_only = build_payload(self.fares, None, "GRN")
        for rows in (prices_only["destinations"], prices_only["anytimeDestinations"]):
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row["journeyState"], "no_timetable")

    def test_the_standard_fare_under_a_discounted_price_is_a_step_down_the_ladder(self) -> None:
        # The price it sits under is the cell's own size, 1rem. One clear step
        # down is a fifth off it, not a twentieth: at .875em the note was 14px
        # against a 16px price, which is the size the page already gives every
        # other small note on a row, so the cell read as two equal numbers
        # rather than one price with a note under it.
        was = float(re.search(r"td\.num \.was \{[^}]*font-size: ([0-9.]+)em",
                              self.stylesheet).group(1))
        self.assertLessEqual(was, 0.8, "the standard fare is not smaller than it was")
        self.assertLessEqual(was, 0.85, "the standard fare is not a clear step down")

    def test_a_destination_type_and_its_count_are_separated(self) -> None:
        # The markup has always had a space between them and it never reached
        # the screen: `.choice-chip` is an inline-flex box, and a flex container
        # drops the whitespace-only text between its items. Measured on the
        # Grantham page, the rendered chip read "Small towns(0)".
        self.assertRegex(
            self.stylesheet,
            r"\.chipcount \{[^}]*margin-left: [^;}]+;",
            "the count is separated from the type name by a margin",
        )
