"""N8: the two railcard checks that encoded the old decision.

Both asserted that a card which cannot cover the party on screen is *absent*
from the selector. That was ADR-0052's choice, and it is what `n2` reverses:
Two Together is two adults exactly, so on the one-adult default page it was the
only card the list lost, and a reader who owns it could not find out the page
prices it.

The property both checks were really protecting is kept and now stated
directly: every card the feed prices is in the list, and one that cannot cover
the party on screen is marked and cannot be chosen. A disabled option cannot
hold a value, so nothing downstream can read a card price nobody could buy --
which is the whole of what removal was doing for the reader.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD_MENU = """    // Q2: a railcard is one of a collection the reader picks from, nothing is
    // selected by default, and a card whose own feed record does not cover the
    // party on screen is not offered for it.
    const cardChoice = await page.locator("#railcardChoice").isVisible();
    const menu = await page.evaluate(() => {
      const select = document.getElementById("railcardSelect");
      const adults = document.querySelector('input[name="unit"]:checked').value === "party" ? 2 : 1;
      return {
        options: Array.from(select.options).map((o) => ({ value: o.value, label: o.textContent })),
        value: select.value,
        disabled: select.disabled,
        help: document.getElementById("railcardHelp").textContent,
        adults,
        // Every card the feed prices, and the ones this party can actually use.
        // A card whose own bounds exclude the party on screen is not offered:
        // it is not that the feed forgot it.
        offered: (DATA.railcards || []).map((c) => c.key),
        forParty: (DATA.railcards || [])
          .filter((c) => c.minAdults <= adults && adults <= c.maxAdults)
          .map((c) => c.key),
      };
    });
    check(
      "the railcard control offers every card this party can use, and one 'none' option",
      cardChoice
        ? menu.offered.length > 0 &&
          menu.options.length === menu.forParty.length + 1 &&
          menu.options[0].value === "" &&
          menu.options.slice(1).every((o, i) => o.value === menu.forParty[i])
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): offered ${JSON.stringify(menu.forParty)} of ${JSON.stringify(menu.offered)}; ${JSON.stringify(menu.options)}`
    );"""

NEW_MENU = """    // Q2: a railcard is one of a collection the reader picks from, nothing is
    // selected by default, and a card whose own feed record does not cover the
    // party on screen is listed but cannot be chosen for it.
    const cardChoice = await page.locator("#railcardChoice").isVisible();
    const menu = await page.evaluate(() => {
      const select = document.getElementById("railcardSelect");
      const adults = document.querySelector('input[name="unit"]:checked').value === "party" ? 2 : 1;
      return {
        options: Array.from(select.options).map((o) => ({
          value: o.value,
          label: o.textContent,
          disabled: o.disabled,
        })),
        value: select.value,
        disabled: select.disabled,
        help: document.getElementById("railcardHelp").textContent,
        adults,
        // Every card the feed prices, and the ones this party can actually use.
        // Every priced card is in the list whatever its bounds; only the usable
        // ones can be chosen. Removal was ADR-0052's answer, and it cost the
        // one card whose bounds are 2 to 2 on a page showing one adult.
        offered: (DATA.railcards || []).map((c) => c.key),
        forParty: (DATA.railcards || [])
          .filter((c) => c.minAdults <= adults && adults <= c.maxAdults)
          .map((c) => c.key),
      };
    });
    check(
      "the railcard control lists every card this page prices, plus one 'none' option",
      cardChoice
        ? menu.offered.length > 0 &&
          menu.options.length === menu.offered.length + 1 &&
          menu.options[0].value === "" &&
          menu.options.slice(1).every((o, i) => o.value === menu.offered[i])
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): priced ${JSON.stringify(menu.offered)}; ${JSON.stringify(menu.options)}`
    );
    check(
      "and only the cards whose own bounds cover the party on screen can be chosen",
      cardChoice
        ? menu.options.slice(1).every((o) => (o.disabled ? !menu.forParty.includes(o.value) : menu.forParty.includes(o.value)))
        : notExercised("this feed prices no reviewed railcard"),
      `${menu.adults} adult(s): usable ${JSON.stringify(menu.forParty)}; ${JSON.stringify(menu.options)}`
    );"""

OLD_SOLO = """    const solo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="adult"]').checked = true;
        render();
        const select = document.getElementById("railcardSelect");
        return {
          options: Array.from(select.options).map((o) => o.value),
          cards: DATA.railcards.map((c) => ({ key: c.key, min: c.minAdults, max: c.maxAdults })),
          help: document.getElementById("railcardHelp").textContent,
        };
      })
      : null;
    // S15: a card that needs two travellers cannot price one reader's journey,
    // so it is not in the list for a party of one rather than left there to be
    // picked and then ignored. The bounds are the feed's own records.
    check(
      "one adult is offered only the cards whose own bounds cover one adult",
      cardChoice
        ? solo.options.slice(1).every((key) => {
            const card = solo.cards.find((c) => c.key === key);
            return card && card.min <= 1 && 1 <= card.max;
          }) &&
          solo.cards
            .filter((c) => c.min > 1)
            .every((c) => !solo.options.includes(c.key))
        : notExercised("this feed prices no reviewed railcard"),
      `options=${solo ? solo.options.join(",") : ""}`
    );"""

NEW_SOLO = """    const solo = cardChoice
      ? await page.evaluate(() => {
        document.querySelector('input[name="unit"][value="adult"]').checked = true;
        render();
        const select = document.getElementById("railcardSelect");
        return {
          options: Array.from(select.options).map((o) => ({ value: o.value, disabled: o.disabled })),
          cards: DATA.railcards.map((c) => ({ key: c.key, min: c.minAdults, max: c.maxAdults })),
          help: document.getElementById("railcardHelp").textContent,
        };
      })
      : null;
    // S15: a card that needs two travellers cannot price one reader's journey,
    // so it cannot be chosen for a party of one -- but it is still in the list,
    // saying how many it needs. Removing it meant Two Together, whose bounds
    // are 2 to 2, was absent from every one-adult page, which reads as "this
    // page does not price Two Together" rather than "not for the party you
    // have on screen". The bounds are the feed's own records.
    check(
      "one adult is offered only the cards whose own bounds cover one adult",
      cardChoice
        ? solo.options.slice(1).every((o) => {
            const card = solo.cards.find((c) => c.key === o.value);
            const usable = card && card.min <= 1 && 1 <= card.max;
            return o.disabled === !usable;
          })
        : notExercised("this feed prices no reviewed railcard"),
      `options=${solo ? JSON.stringify(solo.options) : ""}`
    );"""

if __name__ == "__main__":
    patch("tests/browser_test.cjs", [(OLD_MENU, NEW_MENU), (OLD_SOLO, NEW_SOLO)])