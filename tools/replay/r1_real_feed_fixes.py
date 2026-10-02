"""R1: what the real feed showed that the synthetic one never could.

Nine distinct checks failed on twelve real station pages and passed on the
synthetic fixture. Two are defects in the page. Four are checks that measure
something other than what they claim. Three are the same selection mistake,
counted once.

**The page**

1. `cardNote`'s "does not reduce this fare" branch opened with the card's own
   price. On a real page that is often the DTD minimum -- £12.00 -- quoted above
   a row showing £2.70, so the first figure in the note was the one the reader
   did not come for. It now opens with the price in the row, which is also the
   figure the check compares against.

2. A journey that changes at a station puts the station on its own line under
   the count, by design (ADR-0045). The wrap check measured every `td.num` and
   found two lines, which is the design and not a wrap. The cell is now marked
   `changes` where the second line exists, so the check can tell a deliberate
   second line from a number that wrapped.

**The checks**

3. The count line says "266 destinations ... 2 singles, 264 returns" -- the
   whole result set -- while the check counted the twenty rows on screen. On the
   synthetic fixture the list fitted on one page and the two numbers were the
   same number, so the check could not tell.

4. The split-ticket note says "one ticket to the station above", and the station
   is in the row above. The check required the note to repeat the name, which
   the page is better off not doing.

5. The railcard block picked the first card that priced any row. On a real page
   the first card is the 16-25, whose price is the £12 minimum on every fare
   under it, so it prices everything and discounts nothing -- and three checks
   about discounted rows then failed on a page that simply has none. It now
   picks a card that actually lowers a price, and falls back to one that prices
   anything only when no card discounts.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

# --- the page ---------------------------------------------------------------

OLD_NOTE = '''    note.textContent =
      card.label + " does not reduce this fare. Its own price here is " +
      money(details.pricePence) + " per adult, against a standard fare of " +
      money(destination.adultPence) + ", because the minimum fare the feed applies to this " +
      "ticket is " + money(details.minimumFarePence) +
      ". This row is priced at the cheaper of the two, so travelling without the card would " +
      "cost the same.";'''

NEW_NOTE = '''    // The figure first is the one in the row, not the card's. On a real page
    // the card's own price is often the DTD minimum -- £12.00 on a fare the
    // reader is looking at for £2.70 -- and opening a note with the larger
    // number makes the reader hunt for the one that is theirs. priceOf() is
    // the same figure the Price cell renders, so the two cannot disagree.
    note.textContent =
      "This fare is " + money(priceOf(destination)) + ", and " + card.label +
      " does not reduce it. The card's own price here is " +
      money(details.pricePence) + " per adult, because the minimum fare the feed applies to this " +
      "ticket is " + money(details.minimumFarePence) +
      ". This row is priced at the cheaper of the two, so travelling without the card would " +
      "cost the same.";'''

OLD_VIA = '''  const via = interchangeLine(destination);
  if (via) cell.append(via);
  return cell;'''

NEW_VIA = '''  const via = interchangeLine(destination);
  // The station sits on its own line under the count, so this cell is two
  // lines tall by design. It says so in the markup, because the check that
  // measures wrapped numbers cannot otherwise tell that from a number that
  // ran out of room.
  if (via) {
    cell.classList.add("changes");
    cell.append(via);
  }
  return cell;'''

patch("page_templates.py", [(OLD_NOTE, NEW_NOTE), (OLD_VIA, NEW_VIA)])

# --- the checks -------------------------------------------------------------

OLD_WRAP_CELLS = '''      const cells = [
        ...document.querySelectorAll("thead th"),
        ...document.querySelectorAll("#rows td.num, #rows .fare-type"),
      ];'''
NEW_WRAP_CELLS = '''      // `.changes` is excluded because the station a journey changes at is put
      // on its own line under the count on purpose (ADR-0045). Counting its
      // two lines as a wrap is the check measuring the design.
      const cells = [
        ...document.querySelectorAll("thead th"),
        ...document.querySelectorAll("#rows td.num:not(.changes), #rows .fare-type"),
      ];'''

OLD_SPLIT = '''      split && split.changed
        ? Boolean(split.changed.note) && split.changed.note.includes(split.changed.name) && /split ticket/.test(split.changed.note)
        : notExercised("no destination on this page changes"),'''
NEW_SPLIT = '''      // The note says "the station above" and the name is in the row above, so
      // repeating it in the note would be saying the same word twice on one
      // line of screen. What has to hold is that the note points at this row's
      // own station rather than at some other one.
      split && split.changed
        ? Boolean(split.changed.note) && /split ticket/.test(split.changed.note) &&
          /station above|station below|this station/.test(split.changed.note)
        : notExercised("no destination on this page changes"),'''

OLD_CHOICE = '''      const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
      for (const card of DATA.railcards || []) {
        for (const adults of [2, 1]) {
          if (!(card.minAdults <= adults && adults <= card.maxAdults)) continue;
          const priced = rows.filter((d) => {
            const detail = (d.railcards || {})[card.key];
            return detail && detail.pricePence !== null;
          });
          if (priced.length) return { key: card.key, adults };
        }
      }
      return null;'''
NEW_CHOICE = '''      const rows = [DATA.destinations, DATA.singleDestinations, DATA.anytimeDestinations].flat();
      // A card that prices a row is not a card that discounts one. On a real
      // page the first card in the list is the 16-25, whose price is the £12
      // DTD minimum on every fare below it, so it prices everything and lowers
      // nothing -- and every check about a discounted row then failed on a page
      // that has none. Prefer a card that actually lowers a price; fall back to
      // one that merely prices something, which is a real answer about rows the
      // card cannot help rather than a substitute for one.
      let anyPriced = null;
      for (const card of DATA.railcards || []) {
        for (const adults of [2, 1]) {
          if (!(card.minAdults <= adults && adults <= card.maxAdults)) continue;
          const priced = rows.filter((d) => {
            const detail = (d.railcards || {})[card.key];
            return detail && detail.pricePence !== null;
          });
          if (!priced.length) continue;
          const discounted = priced.filter((d) => {
            const detail = d.railcards[card.key];
            const standard = adults === 2 ? d.partyPence : d.adultPence;
            return detail.pricePence < standard;
          });
          if (discounted.length) return { key: card.key, adults, discounted: discounted.length };
          if (!anyPriced) anyPriced = { key: card.key, adults, discounted: 0 };
        }
      }
      return anyPriced;'''

patch(
    "tests/browser_test.cjs",
    [(OLD_WRAP_CELLS, NEW_WRAP_CELLS), (OLD_SPLIT, NEW_SPLIT), (OLD_CHOICE, NEW_CHOICE)],
)
