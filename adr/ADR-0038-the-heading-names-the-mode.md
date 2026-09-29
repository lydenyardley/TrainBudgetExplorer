# ADR-0038: The heading names the mode, and it is a spec line

**Status:** Accepted
**Date:** 29 September 2026
**Relates to:** ADR-0019 (one page per station), ADR-0027 (the browser suite
covers the template), ADR-0039 (the chooser and a station page are one page with
different content)

## Context

The heading was a question: *Where can we go for up to £20 from GRANTHAM?* It is
accurate, it keeps the two editable slots inside the page's own sentence, and it
has one defect a reader notices before any of its virtues: it never says **train**.
Nothing in it does. The word appeared 90px below it, in the introduction, at body
size and in the muted colour — so the largest text on the page described a
journey of any kind, and the page's actual subject was a footnote under it.

The second problem was length. Nine words of sentence for three facts, and the
six words of scaffolding came before either of the two things the reader came to
set. The reader's eye does find the amount and the station, because they are the
only accent-coloured and underlined words in the line — but they arrive after
"Where can we go for up to", which is a sentence about nothing.

Third: it is also the tab title (C15), and a tab that reads *Where can we go from
GRANTHAM for up to £20?* is a sentence doing a label's job.

## Decision

**The heading is a spec line: what the page is, what it costs, and where from.**
*Train fares · up to £20 · from GRANTHAM*.

1. **The mode is the first two words.** "Train fares" is the subject of the page
   and the first thing read, so the page is about train journeys before it is
   about a budget or a station. It also states the *kind* of number: these are
   fares, not a journey price, not a ticket price.
2. **The cap keeps "up to".** The filter admits a fare exactly at the ceiling, so
   "up to" is the wording that matches the behaviour (C21) — it was the one part
   of the old sentence that could not be cut for brevity, and it survives.
3. **The three parts are separated by a muted dot**, half the heading's size and
   middle-aligned. At six rem a separator in the text colour is as loud as the
   words it separates, and a full-size dot is a disc the width of a letter, which
   reads as a bullet. The separators are `aria-hidden`: the three parts are one
   sentence to a reader, and "middle dot" is not a word the page means to say.
4. **The break is written down, not balanced.** `text-wrap: balance` chose
   between the legal splits by evenness, and both options it liked are wrong: one
   starts the second line with the dot, which reads as a bullet, and the other
   splits "up to" from the amount it qualifies. So "up to" and the amount sit in
   one `white-space: nowrap` box together with the dot that follows them, and the
   only break the heading has is the one before the origin. A word joiner was
   tried first and was not enough: the wrap opportunity is at the *edge* of a
   field's inline box, before anything that follows it, so the joiner itself
   started the second line. Two lines, the same two, at every width.
5. **The tab titles follow**: *Train fares up to £20 from GRANTHAM* on a station
   page, *Train fares up to £20 · pick your station* on the chooser. The figure
   is still written from the same resolved budget as the heading and the outgoing
   links (C15); what is gone is the question mark, which belonged to a sentence
   the heading no longer is.

## Consequences

- **The question form is gone from the page identity.** ADR-0019 quotes the old
  wording where it argues that the origin belongs above the controls as page
  identity, and that argument is unchanged — the origin is still in the heading,
  still above the controls. Only the sentence around it moved.
- The headless-wording guard changed shape rather than disappearing. The test
  that asserted the page says "up to" and never "under" now reads it off the
  heading itself, in the same pass, so the guard is on the string a reader sees
  rather than on a sentence that happens to contain it.
- The browser suite's heading check was reading `textContent`, which cannot see
  an input's value: with the amount now inside the sentence, the check had to
  compose the sentence the reader sees by putting each field's value where the
  field sits, and skipping the hidden text that exists only for a name. It is a
  stronger check for having been forced to be one.
- A dot written as a separator is a promise about line breaking, and the promise
  is only kept if the box model is told about it. Two of the three attempts to
  keep it either glued the joiner to the following text or let the browser break
  between the field and the dot, and both were visible only by looking at the
  rendered page. Layout decisions that depend on where a line may break need the
  rendered page, not the markup.
