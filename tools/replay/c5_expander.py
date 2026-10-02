"""C5: one voice in the row's disclosure, and the feed's words in the record.

Opening one row used to produce three paragraphs saying the same thing in
three registers -- a sentence in the page's voice, the feed's restriction
description, and the restriction's validity text quoted in capitals -- with the
fare type repeated from the column beside it. The panel now opens with one
sentence, adds the condition only when there is one, and files the feed's own
wording in the record, which is the part a reader opens to audit rather than to
decide.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from patch import patch  # noqa: E402

OLD_SENTENCE = '''// The fare in words, inside the row's own disclosure. The pointer C07 asked
// for is kept, because it is still true: a restricted fare's condition is the
// next thing in this same panel, not a column away.
function fareSentence(destination) {
  if (destination.isAdvance) return "Advance single — choose a qualifying train; price and availability can change";
  if (destination.restrictionCode) return "Restricted fare — condition below";
  if (destination.quality === "outbound single") return "Standard outbound single";
  if (destination.quality === "unrestricted Anytime Day Return") return "Unrestricted Anytime Day Return";
  return "Standard return fare";
}'''

NEW_SENTENCE = '''// The fare in words, inside the row's own disclosure. It is a full sentence
// because it is the only thing the panel says before the condition: a fragment
// with a semicolon in it was read as two facts of equal weight, and the second
// half of it ("price and availability can change") was the one a reader needed
// before deciding whether to trust the price at all.
function fareSentence(destination) {
  if (destination.isAdvance) {
    return "Advance single: you choose the train, and the price and availability can change.";
  }
  if (destination.restrictionCode) return "Restricted fare \\u2014 the condition is below.";
  if (destination.quality === "outbound single") return "Standard outbound single, with no conditions in the feed.";
  if (destination.quality === "unrestricted Anytime Day Return") {
    return "Unrestricted Anytime Day Return: valid on any train on the route.";
  }
  return "Standard return fare, with no conditions in the feed.";
}'''

OLD_DETAILS = '''  const fare = document.createElement("p");
  fare.className = "fare-line";
  fare.textContent = fareSentence(destination);
  // S19: what the reader has to know to rule the fare in or out, in sentences.
  const readable = document.createElement("p");
  readable.className = "condition";
  readable.textContent = restricted
    ? (destination.restrictionDescription || "This fare carries a restriction code; check the seller's conditions before buying.")
    : "No travel conditions on this fare in the feed.";
  panel.append(fare, readable);
  // append() would stringify a null argument into the word "null", so the
  // optional note is added only when there is one to add.
  const validity = validityNote(destination);
  if (validity) readable.append(validity);
  const split = splitNote(destination);'''

NEW_DETAILS = '''  const fare = document.createElement("p");
  fare.className = "fare-line";
  fare.textContent = fareSentence(destination);
  panel.append(fare);
  // S19: what the reader has to know to rule the fare in or out, in sentences.
  // Said only when there is a condition to rule out: an unrestricted fare used
  // to open with a second paragraph saying there was nothing to read, which is
  // the same information as silence, said in a line.
  if (restricted) {
    const readable = document.createElement("p");
    readable.className = "condition";
    readable.textContent = destination.restrictionDescription ||
      "This fare carries a restriction code; check the seller's conditions before buying.";
    panel.append(readable);
  }
  const split = splitNote(destination);'''

OLD_FEED_RECORD = '''  add("Ticket", destination.ticket);
  add("Restriction", destination.restrictionCode || "none");
  add("Route", destination.routeCode);
  add("Priced as", destination.quality);
  add("Times", destination.journeyState);
  const rule = railcardRuleFor(destination);
  if (rule) add("Railcard rule", rule);
  details.append(summary, list);
  return details;
}'''

NEW_FEED_RECORD = '''  add("Ticket", destination.ticket);
  add("Restriction", destination.restrictionCode || "none");
  add("Route", destination.routeCode);
  add("Priced as", destination.quality);
  add("Times", destination.journeyState);
  // C08: what the condition permits, in the feed's own words. It was a third
  // paragraph under the row's own, in capitals, between a sentence and a code,
  // and it was the only part of the three that could not be paraphrased without
  // a licencee's risk. It is here now: still verbatim, still present, and
  // behind the record rather than in front of the decision.
  const validity = validityNote(destination);
  if (validity) {
    const dt = document.createElement("dt");
    dt.textContent = "In the feed\\u2019s words";
    const dd = document.createElement("dd");
    dd.append(validity);
    list.append(dt, dd);
  }
  const rule = railcardRuleFor(destination);
  if (rule) add("Railcard rule", rule);
  details.append(summary, list);
  return details;
}'''

OLD_VALIDITY = '''  const note = document.createElement("span");
  note.className = "validity";
  note.append(lines.join(" "));
  return note;
}'''

NEW_VALIDITY = '''  const note = document.createElement("span");
  note.className = "validity";
  note.append(lines.join(" "));
  return note;
}'''

OLD_KIND = '''function fareTypeCell(destination) {
  const cell = document.createElement("td");
  cell.className = "fare-type";
  cell.dataset.label = "Fare type";
  const kind = document.createElement("span");'''

NEW_KIND = '''function fareTypeCell(destination) {
  const cell = document.createElement("td");
  cell.className = "fare-type";
  cell.dataset.label = "Fare type";
  cell.dataset.kind = destination.isAdvance ? "advance"
    : destination.restrictionCode ? "restricted" : "regular";
  const kind = document.createElement("span");'''

patch(
    "page_templates.py",
    [
        (OLD_SENTENCE, NEW_SENTENCE),
        (OLD_DETAILS, NEW_DETAILS),
        (OLD_FEED_RECORD, NEW_FEED_RECORD),
        (OLD_KIND, NEW_KIND),
    ],
)
