# ADR-0037: The reader chooses the palette, and dark is the default

**Status:** Accepted
**Date:** 28 September 2026
**Relates to:** ADR-0027 (the browser suite covers the template), ADR-0033 (one
self-contained file per route), ADR-0036 (the NRE mark's plate)

## Context

The page had exactly one palette switch, and the reader did not hold it:
`prefers-color-scheme`. A reader whose system said light got the light page, and
there was nothing on the page to change it. A person reading fares on a train at
night, in a browser that reports light because the OS does, is stuck with a page
that shines at them — and the fix is in system settings, not on the page.

That is a small thing to be asked for and an awkward thing to build, because the
palette is not one declaration. It is nine colour tokens, and the previous
arrangement held each of them twice: once in a `:root` block and once inside
`@media (prefers-color-scheme: dark)`. Adding a third state — "the reader asked
for light" — to a token list written twice is how palettes drift, and the drift
is invisible: a token only the light block sets is a token the dark page never
redefines, which is exactly the C14 defect the project already fixed once.

There is also a second question that the request surfaced: the NRE mark is dark
blue on a fixed fill, so a dark page needs to know what to put behind it. The
mark cannot be recoloured — an edited mark is not the mark NRE licensed (ADR-0036)
— so what can move is the plate under it.

## Decision

**One token list, both schemes in it, and a switch that names the scheme. Dark
unless the reader says otherwise.**

1. **Each colour token is written twice in one declaration**: the plain light
   value first, then `light-dark(light, dark)`. The first is what a browser
   without `light-dark()` uses, so an old browser gets the light page rather
   than an invalid value resolving to nothing; the second is what a browser with
   it uses, and it carries both palettes from a single list. The dark palette can
   no longer drift from the light one, because they are one line.
2. **`:root` asks for `color-scheme: light dark`**, so a reader with no stored
   choice gets their system preference, and `:root[data-theme="…"]` names the
   scheme the reader chose. Naming it is the whole switch: the tokens are already
   resolved, and it also moves the form controls, the scrollbars and the canvas,
   which a token override alone would not.
3. **The default is dark.** This is a page read at night, on a phone, on a
   train. A reader who wants light presses one button.
4. **The choice is stored and read before the first paint.** The head block sets
   `data-theme` from `localStorage` in the same parse as the stylesheet, so
   there is no flash of the other palette on any visit. Storage can throw — a
   private window, a `file://` page with storage blocked — and then the default
   stands, which is what a default is for.
5. **The control is in the flow, at the top right, and hidden until it is
   wired.** It is a `role="switch"` button named by hidden text, so a screen
   reader says "Dark theme, switch, on" and a sighted reader sees a moon. It
   ships `hidden` and the script reveals it, because a button that cannot work
   without JavaScript is a control that lies — the same defect as the Change
   button this project removed in favour of text last week. And it is *not*
   `position: fixed`: pinned in the corner it sat on top of whatever the reader
   scrolled there, and on a phone the destination-type chips land underneath it,
   so a tap meant to choose a destination type chose the palette instead. The
   browser suite found that one, and it would have been found by a reader
   eventually.
6. **The plate under the NRE mark is a token, `--logo-plate`, and it follows the
   palette**: white in light, a near-white in dark, so the chip reads as a chip
   rather than as a hole in the footer. The mark's own colours never move. In the
   light palette the plate is white on a white page, so it also carries a 1px
   edge — without one it measured 1.00:1 against the background and was not a
   plate at all, which the legibility check caught.

   **Amended 28 September 2026.** `--logo-plate` is gone. The credit is dark in
   both palettes — `--nre-plate: #141b3d` with `--nre-ink: #cdd6ff` — because
   following the palette was solving the wrong problem: a plate that changes
   colour with the theme is a plate that has to be re-earned in each theme, and
   the light one was a white box on a white page, held together only by its
   edge. One chip that is dark everywhere is one thing, it is legible at 12.4:1
   instead of at whatever the page behind it happens to be, and it reads as
   part of the design rather than as a hole in the footer. It is the one pair of
   colours in the palette that is deliberately not a `light-dark()` pair, and the
   test says so. The mark was reversed to achieve it (ADR-0036, amended twice),
   which stood as an open question with NRE rather than a settled one.

   **Amended 16 October 2026.** The ink is white, not the pale blue (ADR-0036,
   amended a third time). The guidelines permit three colours — blue, black and
   white — so `#cdd6ff` was none of them and the reversal was never needed to
   be an open question: `--nre-ink` is `#ffffff`, still one fixed chip in both
   palettes, and the legibility check now measures white against the plate.

## Consequences

- The palette is one list, so a token cannot be added to the light page and
  forgotten in the dark one. The test that used to count `:root` blocks now
  asserts every colour token has a `light-dark()` counterpart, which is the
  C14 check in the shape the code now has.
- The suite drives the switch rather than the OS preference, so it tests the
  control a reader uses instead of a media query. Five new checks: the control
  exists and is shown, it is a named switch whose `aria-checked` is the palette
  the page is painting, a first visit with empty storage is dark, the target is
  44px, and the choice survives a reload. The mark's legibility is measured in
  each scheme — 3:1 for the mark on its plate, and the plate has to be findable.
  Measuring it properly took two attempts and found two defects: the check first
  read colours out of the computed string, which silently misreads a
  `color-mix()` border because the browser reports those in a notation whose
  numbers are not channels; and it then passed an array to `fillStyle`, which is
  not a colour, so the canvas kept the previous one and a plate with a
  transparent border passed. Both were found by tampering with the built page and
  running the suite against the tampered copy, which is now the standing way to
  show a browser check has teeth.
- One test-side consequence worth recording: the theme block is a script in the
  head, so "the page's script" stopped being the first `<script>` in the file.
  Fourteen call sites read that slice and were reading the theme block. They now
  go through `page_script()` and `page_markup()`, which say what they mean.
- A reader with JavaScript off gets the dark page and no switch. That is the
  right way round for this page: its entire function is a script, and a dead
  button is worse than an absent one.
