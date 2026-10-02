"""N1: one rule per row on a phone, drawn by the row.

Below 44rem the table reflows into stacked rows. The stacking was a flex row,
and each cell kept the `border-bottom` the table gave it, so every cell drew a
horizontal line at its own height. Measured at 360px on the Grantham page:

    row height 216px, cells 41 / 41 / 41 / 65 / 41 / 48px

Six rules, at six heights, none of them reaching the row's own line at the
bottom. That is the mismatched-lines report.

Two things cause it, and both are fixed here. The borders: the cells draw
nothing and the row draws the one rule, which is the only arrangement where
the lines can line up. The heights: the cells were flex items that wrapped
wherever they liked, so a row's cells were six different heights. Each is now
a grid of two fixed columns, which makes it exactly as tall as its own content
and no taller.

The columns are a label track and a value track of the same width in every
cell, so the values line up beside one another down the page and the labels
form one straight edge. The stacked halves of a cell -- the standard fare under
a discounted price, the change station under the count -- take their own line in
the value track, so they never read as two values side by side.

The panel a row opens had a rule of its own too, so opening one destination
drew a second line across the page and read as another destination. It now
belongs to the row above it.
"""

import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch import patch  # noqa: E402

OLD_ROWS = """    tr { display: flex; flex-wrap: wrap; align-items: baseline; gap: .1rem .75rem;
         padding: .5rem 0; border-bottom: 1px solid var(--line); }
    td[data-label]::before { content: attr(data-label) " "; color: var(--muted); font-size: .78rem;
                             text-transform: uppercase; letter-spacing: .04em; }
    td:first-child { flex: 1 1 100%; padding-left: 0; }
    td.num { text-align: left; }
    /* On a phone the numbers and the fare type share the line under the
       destination, and the actions take the line below them: `margin-left:
       auto` pushed them to the right edge, which is where the thumb is, and
       where a stray tap buys a ticket. */
    td:last-child { margin-left: 0; }
    tr.detail td { flex: 1 1 100%; padding: .5rem 0; }
"""

NEW_ROWS = """    /* One rule per row, and the row is what draws it. Every cell kept the
       border the table gave it and drew a line at its own height, so a stacked
       row carried up to six horizontal lines at six different heights, none of
       them reaching the row's own. The cells are the row's contents now and
       draw nothing, which is the only arrangement in which the lines line up.
       `th, td` rather than `td`, because the base rule this cancels is a
       `th, td` pair and a media query adds no specificity of its own. */
    th, td { border-bottom: 0; }
    /* One cell per line, the full width, rather than a flex line that wrapped
       wherever it happened to fit. The wrap is what made a row's cells
       different heights from each other. */
    tr { display: block; padding: .55rem 0; border-bottom: 1px solid var(--line); }
    /* Two columns of the same width in every cell: the label, then the value.
       A fixed track rather than `max-content`, so "CHANGES" and "PRICE" do not
       each size a column of their own and leave the values ragged. */
    td { display: grid; grid-template-columns: 5rem minmax(0, 1fr); column-gap: .55rem;
         align-items: baseline; border: 0; padding: 0; }
    td[data-label]::before { content: attr(data-label); color: var(--muted); font-size: .78rem;
                             text-transform: uppercase; letter-spacing: .04em; }
    /* Every element inside a cell is part of its value, so it belongs in the
       value track and takes its own line there when there is more than one.
       This is what keeps the standard fare under a discounted price, and the
       change station under the count, off the same line as the number beside
       it -- the reason both are `display: block` on a wide screen. */
    td > * { grid-column: 2; }
    /* The destination and the row's actions carry no label, so they take the
       whole width rather than the value track. */
    td:first-child, td:last-child { display: block; }
    td.num { text-align: left; }
    /* The panel a row opens belongs to the row above it. It had a rule under it
       of its own, so opening one destination drew a second line across the page
       and read as another destination. The actions stay inline in the cell
       rather than pushed to the right edge, which is where the thumb is and
       where a stray tap buys a ticket. */
    tr.detail { padding: 0; border-bottom: 0; }
    /* `border-bottom` is named here and not left to the `th, td` rule above,
       because the base `tr.detail td` rule that this cancels is one selector
       deeper and wins on specificity whatever order the two are written in. */
    tr.detail td { padding: .5rem 0 .55rem; border-bottom: 0; }
"""

if __name__ == "__main__":
    patch("page_templates.py", [(OLD_ROWS, NEW_ROWS)])