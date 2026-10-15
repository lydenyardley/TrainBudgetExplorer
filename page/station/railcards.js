// The party and the railcard: who is travelling, which cards this build
// priced, the party each card covers, and the price that comes out of the
// two. Every other panel reads the price from here rather than deciding it.

// Q2: the railcard is a select over the reviewed collection rather than one
// checkbox for one card. Its options are written from the payload below, so the
// control can only ever offer a card this build priced.
const railcardSelect = document.getElementById("railcardSelect");
const railcardChoice = document.getElementById("railcardChoice");
// The browser remembers the reader's card between pages. The key is
// per-origin because a reader from one station is answering the same question
// as a reader from another, and a stored card must not travel to a page whose
// feed priced nothing for it.
const RAILCARD_MEMORY = "tbe.railcard.";
// The one drawn disclosure mark, in the script as well as in the markup. The
// filter bar's chevron is written into the HTML at build time; a row's chevron
// is built when the reader opens the list, so the script needs the same path.
// Both come from the one CHEVRON constant below, because two drawings of a
// chevron is one too many marks to keep in step.
const CHEVRON = __CHEVRON_JS__;
let rememberedCard = null;
try {
  rememberedCard = window.localStorage.getItem(RAILCARD_MEMORY + DATA.origin.crs);
} catch (error) {
  // A browser with storage blocked still gets the control; it just asks again.
  rememberedCard = null;
}

// The collection the page offers, keyed by the code the feed priced it under.
const railcards = (DATA.railcards || []).reduce((all, card) => {
  all[card.key] = card;
  return all;
}, {});
const railcardKeys = Object.keys(railcards);
const noCard = () => railcardSelect.value === "";

// The options are written from the payload, so the control lists the cards this
// build actually priced and nothing else. This runs before the address is read
// (ADR-0052): a card named in a shared link is applied to a select that already
// has an option for it, and a card this feed does not price is dropped rather
// than read as one the reader holds.
if (railcardKeys.length) {
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "No railcard";
  railcardSelect.append(none);
  for (const key of railcardKeys) {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = railcards[key].label;
    railcardSelect.append(option);
  }
  // A remembered card is applied only when this page prices it, so a reader who
  // chose a card on a page that offered it is not silently moved onto a
  // different card where it is absent.
  if (rememberedCard && railcardSelect.querySelector('option[value="' + rememberedCard + '"]')) {
    railcardSelect.value = rememberedCard;
  }
}

// The party a chosen card covers, from the feed's own records for it. A card
// that needs two travellers cannot price one reader's journey, and the page
// says so in the list rather than offering a number nobody could buy: the
// option is there and marked, and cannot be chosen.
function cardCoversParty(card) {
  const adults = unit() === "party" ? 2 : 1;
  return card.minAdults <= adults && adults <= card.maxAdults;
}
function unit() {
  return document.querySelector('input[name="unit"]:checked').value;
}
function priceOf(destination) {
  const party = unit() === "party";
  const base = party ? destination.partyPence : destination.adultPence;
  const card = chosenCard(destination);
  if (card) {
    const cardTotal = card.pricePence * (party ? 2 : 1);
    return Math.min(base, cardTotal);
  }
  return base;
}
// The chosen card's decision for one row, or null when none is chosen, this
// row cannot price it, or the card does not cover the party on screen. A card
// the feed blocked for a fare has no price and is not offered as one.
function chosenCard(destination) {
  if (noCard()) return null;
  const card = destination.railcards && destination.railcards[railcardSelect.value];
  if (!card || card.pricePence === null || card.pricePence === undefined) return null;
  const chosen = railcards[railcardSelect.value];
  return chosen && cardCoversParty(chosen) ? card : null;
}
// Q3: with the card ticked the cell shows what the reader would pay *and* the
// standard fare it came from, so a discounted number never stands alone. With
// the box clear there is one price and no second number, because there is one
// price.
function priceCell(destination) {
  const cell = document.createElement("td");
  cell.className = "num";
  cell.dataset.label = "Price";
  const standard = standardPrice(destination);
  const price = priceOf(destination);
  const amount = document.createElement("span");
  amount.className = "price";
  amount.textContent = money(price);
  cell.append(amount);
  if (price < standard) {
    const was = document.createElement("span");
    was.className = "was";
    was.textContent = " " + money(standard) + " standard";
    cell.append(was);
  }
  return cell;
}
// S15: a railcard covers a named number of adults travelling together, so it
// is a constraint on the party rather than a discount a solo reader can tick.
// The number is the feed's own record for each card rather than a rule this
// page invented, and a card that cannot cover the party on screen is taken out
// of the list rather than left there to be picked and then ignored.
function renderRailcardNote() {
  const note = document.getElementById("railcardNote");
  if (!note) return;
  // The page's own explanation of its numbers, written from the state the rows
  // read rather than from a build-time constant: a railcard holder used to be
  // told no card was selected while every row showed a card price (audit item
  // 24). With no card the payload's paragraph stands, because that one is
  // written for exactly this state.
  if (noCard() || !DATA.railcardMethod) {
    note.textContent = DATA.railcardNote;
    return;
  }
  const chosen = railcards[railcardSelect.value];
  // "Wherever it lowers the fare", not "every price includes it": a card whose
  // minimum fare is above the standard one leaves that row at the standard
  // fare, and the paragraph explaining the numbers cannot be false about a row
  // the reader is looking at (audit item 24).
  note.textContent = "The prices shown apply the " + chosen.label +
    " wherever it lowers the fare. " + DATA.railcardMethod;
}
function syncRailcardParty() {
  const help = document.getElementById("railcardHelp");
  if (!railcardKeys.length) {
    // The sentence stays and says why: "standard fares" with no explanation is
    // the claim the whole page rests on, and a reader who owns a 16-25 card is
    // owed the reason their card is not in the list.
    if (help) {
      help.textContent = "This feed prices no reviewed railcard, so these are standard fares.";
      help.hidden = false;
    }
    if (railcardChoice) railcardChoice.hidden = true;
    railcardSelect.disabled = true;
    return;
  }
  if (railcardChoice) railcardChoice.hidden = false;
  // A card that cannot price the party on screen is removed from the list
  // rather than left there to be picked and then ignored. The feed's own
  // records decide, so the page is not inventing a rule about who travels.
  //
  // The list is rebuilt rather than filtered in place, because the party
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
  if (!help) return;
  if (noCard()) {
    // The action and the memory come first: which card is held changes every
    // price on the page, and what happens to the choice is the fact a reader
    // wants before making it (audit item 16). It says where the choice goes
    // rather than that it goes nowhere, because the card is one of the keys in
    // the address (stateQuery) and the address is read by the host.
    help.textContent = "Choose the card you hold and the fares it lowers are repriced for it. " +
      "This browser remembers your choice and, like the rest of your search, it travels in " +
      "the page's address; until then, every price is a standard fare.";
    return;
  }
  const chosen = railcards[railcardSelect.value];
  const covers = "The " + chosen.label + " in this feed covers " + chosen.minAdults + " to " +
    chosen.maxAdults + " adults";
  help.textContent = covers + ", which matches the party on screen. " + chosen.eligibleCount +
    " destinations receive a lower price with it; open a row's own details for the minimum " +
    "fare and the conditions the feed applies.";
}
