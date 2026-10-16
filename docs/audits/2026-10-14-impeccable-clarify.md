# Clarity audit: the language of every user-facing view

**Date:** 14 October 2026
**Command:** `impeccable clarify`, run over every route rather than one target
**Commit reviewed:** `a6c809c` on `main`
**Pruned:** 15 October 2026. Forty-four of this audit's fifty numbered items were
applied that day, and item 1 had landed in `e20582d` with the rest of the 14
October critiques. Each is held by the commit that carries it
(`git log --grep="audit item"`), and the group-to-artifact mapping is under "The
14 October 2026 clarity audit" in `docs/open-work.md`. Item 8 read a sentence
that was worth leaving as it was, and item 5's choice between warm and blunt was
made in this pass (warm). The numbers keep their original values, so a gap in the
sequence is deliberate. What is below is what the audit still asks for: four
findings that need a person (3's data question, 17, 42 and 44) and one nobody has
taken up yet (23).

## Still open

- **[3, the data half] [P1] The chooser's number and the page's number
  disagree.** The copy half landed: the chooser row now reads *"GRANTHAM GRA 50
  destinations this feed prices"*, so a bare count cannot be read against the
  count line's *"53 destinations for up to £20.00 per adult"*. What is left is the
  arithmetic behind the two. The index counts every priced destination at any
  budget (`_priced_destinations`, the union over the three modes at
  `EVERYTHING_PENCE`) while the page counts what is inside the budget on screen,
  and the synthetic site behaves exactly as that predicts (chooser "5
  destinations", page "4 destinations for up to £20.00 per adult"). The release's 50
  against 53 cannot come from that difference alone, so it is a data question for
  whoever owns the index, and it is question 7 under "What is waiting on a
  person" in `docs/open-work.md`.
- **[17] [P2] The destination-type chips are ONS bands wearing everyday words.**
  Rendered: *All / Cities (2) / Small towns (1) / Coastal & seaside (1) /
  University towns (2) / World heritage (1)* — and on the release page *Towns /
  Villages / Islands / Airports / Nature sites / Transport interchanges / RSPB
  reserves / National Trust / National parks and landscapes*. "Cities" and
  "Villages" are Census 2021 built-up-area size bands, which is not what a reader
  means by either word, and the rule line below explains counts but not the bands.
  Recommendation: one line naming the source ("size of the place, from the 2021
  census"), or rename the four bands so they cannot be read as the ordinary words.
  *Needs a person:* the labels are a product decision, and the chips are written
  from `DESTINATION_TYPE_FILTERS` in `atoc_fare_declarations.py`, the same
  reviewed table the payload's types are keyed by, so a rename is one registry
  edit. Question 8 under "What is waiting on a person".
- **[23] [P2] The price cell packs three facts with no words between them.** With
  a 16-25 card chosen: *"£4.65 £7.00 standard"*. Visually this is a price, a
  struck price and a label; in text order it is three numbers and a word. The word
  "standard" is doing the whole job of saying which is which. *"£4.65 with your
  card (was £7.00)"* is longer but needs no second glance. **Not taken up:** this
  pass was asked for items 1-7, 9-16, 18-22, 24-41 and 43-50, and 23 was not
  among them. The recommendation stands as written.
- **[42] [P2] The built line promises a publication that has not happened.**
  *"This notice describes the build published on 14 October 2026."* Nothing had
  been published when this was read, and `licences/release-clearance.md` was still
  open; the fares route was cleared on 16 October 2026, so the verb becomes true
  when a run reaches the deploy job rather than at build time. The sentence stays
  — the analytics bullets below it are claims about one build — so what is left is
  the wording: "the build dated …", the date without the verb, or the verb kept.
  *Needs a person:* a build that is only ever built locally is not published.
  Question 9 under "What is waiting on a person".
- **[44] [P1] Nothing defines the trade vocabulary the page quotes.** ITX (footer,
  `#feedCoverage`), DTD (provenance, method), RR (the railcard note and rule),
  "feed", "this download", "feed dated", "flow" (`#feedCoverage`: *"140 priced
  flows had no station name in the feed"*), "Priced as", "Feed record", "walk-up
  fare", "NRE". None is glossed on any route, and `docs/glossary.md` already holds
  the reader-facing definitions of several. Recommendation: one short glossary
  inside the method disclosure, and a first-use gloss for the two or three that
  appear above the table. Three of the list moved in this pass: "walk-up fare"
  carries its gloss where it is met (item 30, *"the fare you can buy on the day"*),
  the row's disclosure is labelled *"Feed record (technical details)"* so a reader
  knows which of the two registers they are in (item 26), and the price line says
  *"downloaded"* where the audit read "feed dated" (item 45). The rest still needs
  a person: which terms the audience genuinely knows (the brief says plain language
  without flattening real terminology) is a judgement about rail readers, not a
  style rule. Question 10 under "What is waiting on a person".
