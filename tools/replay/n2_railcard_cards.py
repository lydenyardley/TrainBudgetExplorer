"""N2: every railcard this build prices is in the list; the ones that cannot
price the party on screen are marked, not removed.

`syncRailcardParty` filtered the options by `cardCoversParty`, against the
feed's own `minAdults`/`maxAdults`. On the default page -- one adult -- that
dropped Two Together, whose bounds are 2 to 2, and it was the only card the
selector hid: Six options are priced by both the synthetic and the real feed,
and Five Together's absence from a list of railcards read as "this page does
not price Two Together" rather than "not for the party you have on screen".

ADR-0052 chose removal over leaving a card there to be picked and then
ignored. The guarantee it was protecting is that the page never shows a price
nobody could buy, and `option.disabled` keeps that guarantee exactly as
strictly as removal did -- a disabled option cannot hold a value, so
`priceOf`/`cardFor` can never read one. What it stops doing is hiding a real
card. The option says what it needs, in the feed's own bounds, so the reason is
on screen rather than inferred from an absence.

One adult on screen, of the six cards the feeds price:

    Two Together            2 adults   listed, needs 2 adults, not selectable
    Student Discount Card   1 adult    selectable
    the other four          1-8, 1-2, 1-4, 1-8   selectable
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD = """  // The list is rebuilt rather than filtered in place, because the party
  // control and the card control are two answers to one question and the second
  // has to follow the first. The earlier version computed the offered list and
  // then left the options alone, so a party of two was still offered a card the
  // feed says prices one traveller; the browser suite found it by asking which
  // options a party of two can see.
  const offered = railcardKeys.filter((key) => cardCoversParty(railcards[key]));
  const wanted = railcardSelect.value;
  railcardSelect.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  for (const key of offered) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = railcards[key].label;
    railcardSelect.append(option);
  }
  // The reader's choice survives the rebuild when the party on screen still
  // allows it, and is cleared when it does not.
  railcardSelect.value = offered.includes(wanted) ? wanted : "";
  railcardSelect.disabled = offered.length === 0;
"""

NEW = """  // The list is rebuilt rather than filtered in place, because the party
  // control and the card control are two answers to one question and the second
  // has to follow the first. The earlier version computed the offered list and
  // then left the options alone, so a party of two was still offered a card the
  // feed says prices one traveller; the browser suite found it by asking which
  // options a party of two can see.
  //
  // Every card this build priced is listed, including the ones that cannot
  // price the party on screen. They used to be removed, and the one card the
  // default page lost that way was Two Together -- two adults exactly, on a
  // page showing one -- so a reader who owns it could not find out the page
  // prices it at all. The card is listed and struck out of choosing instead,
  // which keeps ADR-0052's actual guarantee: a disabled option cannot hold a
  // value, so nothing downstream can read a card price nobody could buy. The
  // sentence in the option is the feed's own bound, so the reason is on screen
  // rather than inferred from an absence.
  const adults = unit() === "party" ? 2 : 1;
  const wanted = railcardSelect.value;
  railcardSelect.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  const offered = [];
  for (const key of railcardKeys) {
    const card = railcards[key];
    const option = document.createElement("option");
    option.value = key;
    if (cardCoversParty(card)) {
      option.textContent = card.label;
      offered.push(key);
    } else {
      option.textContent = card.label + (adults < card.minAdults
        ? " (needs " + card.minAdults + " adults)"
        : " (covers up to " + card.maxAdults + " adult" + (card.maxAdults === 1 ? "" : "s") + ")");
      option.disabled = true;
    }
    railcardSelect.append(option);
  }
  // The reader's choice survives the rebuild when the party on screen still
  // allows it, and is cleared when it does not.
  railcardSelect.value = offered.includes(wanted) ? wanted : "";
  railcardSelect.disabled = offered.length === 0;
"""

# The comment above cardCoversParty claimed removal; it now describes marking.
OLD_COMMENT = """// The party a chosen card covers, from the feed's own records for it. A card
// that needs two travellers cannot price one reader's journey, and the page says
// so rather than offering a number nobody could buy.
function cardCoversParty(card) {
  const adults = unit() === "party" ? 2 : 1;
  return card.minAdults <= adults && adults <= card.maxAdults;
}"""

NEW_COMMENT = """// The party a chosen card covers, from the feed's own records for it. A card
// that needs two travellers cannot price one reader's journey, and the page
// says so in the list rather than offering a number nobody could buy: the
// option is there and marked, and cannot be chosen.
function cardCoversParty(card) {
  const adults = unit() === "party" ? 2 : 1;
  return card.minAdults <= adults && adults <= card.maxAdults;
}"""

if __name__ == "__main__":
    patch("page_templates.py", [(OLD_COMMENT, NEW_COMMENT), (OLD, NEW)])