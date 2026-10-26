"""Tests for the link checker.

The verdicts are the whole product. The one that matters most is that a page
which merely looks healthy is never reported as working, because the tool has
never seen a working seller page and has nothing to recognise one by.
"""

from __future__ import annotations

import unittest

from tools.check_links import (
    BLOCKED,
    EXPLANATION,
    FAILURES,
    HTTP_ERROR,
    INCONCLUSIVE,
    NO_JOURNEYS,
    check,
    classify,
    main,
)
from trainbudget.fares.retailer import PROVIDERS


class ClassifyTest(unittest.TestCase):
    def test_a_refusal_is_reported_as_a_refusal(self) -> None:
        body = "<h2>Access is temporarily restricted</h2><p>We have checks to prevent misuse by automated bots.</p>"
        self.assertEqual(classify(200, body), BLOCKED)

    def test_a_captcha_interstitial_is_reported_as_a_refusal(self) -> None:
        self.assertEqual(classify(200, "geo.captcha-delivery.com/interstitial/"), BLOCKED)

    def test_an_error_status_is_an_error(self) -> None:
        self.assertEqual(classify(403, "Forbidden"), HTTP_ERROR)
        self.assertEqual(classify(500, ""), HTTP_ERROR)

    def test_a_request_that_never_arrived_is_an_error(self) -> None:
        self.assertEqual(classify(0, "<urlopen error timed out>"), HTTP_ERROR)

    def test_the_observed_national_rail_failure_is_recognised(self) -> None:
        body = (
            "Outward results, step 1 of 2\n"
            "Error: No matching journeys found. Please re-plan your journey below."
        )
        self.assertEqual(classify(200, body), NO_JOURNEYS)

    def test_a_refusal_outranks_a_page_that_also_says_there_are_no_journeys(self) -> None:
        self.assertEqual(classify(200, "Access is temporarily restricted. No matching journeys found."), BLOCKED)

    def test_an_error_status_outranks_a_page_that_says_there_are_no_journeys(self) -> None:
        self.assertEqual(classify(403, "No matching journeys found"), HTTP_ERROR)

    def test_an_error_string_in_the_app_is_not_a_result(self) -> None:
        # National Rail's shell carries its own "No matching journeys found" in
        # a microcopy dictionary on every response -- measured 9 October 2026:
        # the same shell for every query. Inside a script it is the app's
        # vocabulary, not the search's answer.
        body = (
            "<h1>Search results</h1>"
            '<script type="application/json">{"noResultsOnOutwardMessage":'
            '"No matching journeys on date requested"}</script>'
        )
        self.assertEqual(classify(200, body), INCONCLUSIVE)

    def test_the_error_rendered_into_the_page_is_still_a_result(self) -> None:
        # The other direction of the same fix: a server that renders the error
        # into markup is answering the query, and dropping scripts must not
        # drop that.
        body = (
            '<script>{"m":"No matching journeys found"}</script>'
            '<p role="alert">Error: No matching journeys found. Please re-plan your journey below.</p>'
        )
        self.assertEqual(classify(200, body), NO_JOURNEYS)

    def test_the_unclosed_script_a_truncated_page_leaves_is_not_a_result(self) -> None:
        # The shape the live check actually receives: National Rail's
        # __NEXT_DATA__ script opens at byte 82,334 and the body ends inside it,
        # mid-JSON, so a strip that needs </script> stops right where the error
        # strings are (measured 9 October 2026).
        body = (
            "<h1>Search results</h1>"
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"m":"No matching journeys found. Please re-plan your journey below."}'
        )
        self.assertEqual(classify(200, body), INCONCLUSIVE)

    def test_a_healthy_looking_page_is_inconclusive(self) -> None:
        body = "<h1>Search results</h1><p>Standard from &pound;14.50, departs 09:15, 0 changes</p>"
        self.assertEqual(classify(200, body), INCONCLUSIVE)

    def test_an_empty_healthy_page_is_inconclusive(self) -> None:
        self.assertEqual(classify(200, ""), INCONCLUSIVE)

    def test_there_is_no_verdict_that_means_the_link_works(self) -> None:
        # Every verdict is either a proven failure or an admission that the check
        # could not tell. Nothing here can certify a link.
        self.assertEqual(set(EXPLANATION), {BLOCKED, HTTP_ERROR, NO_JOURNEYS, INCONCLUSIVE})
        self.assertEqual(FAILURES, {NO_JOURNEYS, HTTP_ERROR})
        self.assertNotIn(INCONCLUSIVE, FAILURES)
        self.assertNotIn(BLOCKED, FAILURES)


class CheckTest(unittest.TestCase):
    """No network is touched: the fetch is injected."""

    def test_the_check_opens_the_link_the_page_would_build(self) -> None:
        seen: list[str] = []

        def fake(url: str, *, timeout: int) -> tuple[int, str]:
            seen.append(url)
            return 200, "Search results"

        url, status, verdict = check("national_rail", "GRA", "NOT", fetch_body=fake)
        self.assertEqual(seen, [url])
        self.assertEqual(status, 200)
        self.assertIn("origin=GRA", url)
        self.assertIn("destination=NOT", url)
        self.assertEqual(verdict, INCONCLUSIVE)

    def test_a_fallback_check_opens_the_sellers_own_search_page(self) -> None:
        seen: list[str] = []

        def fake(url: str, *, timeout: int) -> tuple[int, str]:
            seen.append(url)
            return 200, ""

        url, _status, _verdict = check(
            "national_rail", "GRA", "NOT", mode="fallback", fetch_body=fake
        )
        self.assertEqual(url, PROVIDERS["national_rail"].fallback_url)
        self.assertEqual(seen, [url])
        self.assertNotIn("?", url)

    def test_every_seller_has_a_fallback_page_to_be_checked_against(self) -> None:
        for key, provider in PROVIDERS.items():
            self.assertTrue(provider.fallback_url, f"{key} has no fallback page recorded")
            self.assertTrue(provider.fallback_url.startswith("https://"))


class MainTest(unittest.TestCase):
    def test_a_bad_date_stops_before_any_request(self) -> None:
        self.assertEqual(main(["--date", "not-a-date"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
