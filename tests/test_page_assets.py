"""The page's CSS and JS are files under page/, and the module inlines them.

F1 of the 8 October 2026 agent-efficiency audit: the station page's JavaScript
was 2,900 lines inside a Python string, where no editor, linter or search could
see it and no syntax check reached it, and half of every page fix landed in the
file that held it. The blocks are files now, read at import. These tests hold
what the move depends on: each file is the bytes the page ships, and a checkout
that hands back CRLF cannot rewrite every page of a release.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import page_templates

#: Each file under page/, and the string the page ships it in. A file that is
#: not in its holder is a block that stopped being read, which leaves the page
#: unstyled or unwired rather than failing anywhere near the edit. The station
#: route's script is one file per panel under page/station/, concatenated into
#: the one `_TEMPLATE` in the order page_templates.py names.
ASSETS = {
    "shared.css": "SHARED_CSS",
    "station.css": "STATION_CSS",
    "station/payload.js": "_TEMPLATE",
    "station/railcards.js": "_TEMPLATE",
    "station/budget.js": "_TEMPLATE",
    "station/service-day.js": "_TEMPLATE",
    "station/filters.js": "_TEMPLATE",
    "station/ticket-modes.js": "_TEMPLATE",
    "station/format.js": "_TEMPLATE",
    "station/table.js": "_TEMPLATE",
    "station/row-cells.js": "_TEMPLATE",
    "station/fare-panel.js": "_TEMPLATE",
    "station/row-actions.js": "_TEMPLATE",
    "station/provenance.js": "_TEMPLATE",
    "station/picker.js": "_TEMPLATE",
    "station/shortlist.js": "_TEMPLATE",
    "station/url-state.js": "_TEMPLATE",
    "station/wiring.js": "_TEMPLATE",
    "chooser.js": "_CHOOSER_TEMPLATE",
    "chooser.css": "_CHOOSER_TEMPLATE",
    "privacy.css": "_PRIVACY_TEMPLATE",
    "theme.js": "SHARED_THEME",
}


class PageAssetTest(unittest.TestCase):
    def test_every_asset_is_a_file_that_lands_in_the_page(self) -> None:
        for asset, holder in ASSETS.items():
            with self.subTest(asset=asset):
                self.assertTrue(
                    Path(page_templates._PAGE_ASSETS, asset).is_file(),
                    f"page/{asset} is missing from the module's own directory",
                )
                text = page_templates._page_file(asset)
                self.assertGreater(len(text.strip()), 0, f"page/{asset} is empty")
                self.assertIn(
                    text,
                    getattr(page_templates, holder),
                    f"page/{asset} is not the block {holder} holds",
                )

    def test_the_module_reads_every_asset_it_holds(self) -> None:
        # A file nobody reads is a block that was moved and then edited to no
        # effect, so the directory holds the module's assets and nothing else.
        # The station route's script is one file per panel under a
        # subdirectory, so the walk goes below the first level: a check that
        # read only the files beside it would miss every panel added there.
        on_disk = {
            path.relative_to(page_templates._PAGE_ASSETS).as_posix()
            for path in page_templates._PAGE_ASSETS.rglob("*")
            if path.is_file()
        }
        self.assertEqual(on_disk, set(ASSETS))

    def test_no_asset_carries_a_carriage_return(self) -> None:
        # The built page's bytes are the template's bytes, and the templates use
        # LF. A file that gained a CR would change every page that inlines it.
        for asset in ASSETS:
            with self.subTest(asset=asset):
                raw = Path(page_templates._PAGE_ASSETS, asset).read_bytes()
                self.assertNotIn(b"\r", raw, f"page/{asset} has a carriage return")

    def test_a_crlf_checkout_cannot_change_a_page(self) -> None:
        # Windows checks this repository out with CRLF (core.autocrlf), and a
        # release built there must be the release built anywhere else.
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "sample.css").write_bytes(b"a { color: red; }\r\nb { color: blue; }\r\n")
            with mock.patch.object(page_templates, "_PAGE_ASSETS", Path(folder)):
                self.assertEqual(
                    page_templates._page_file("sample.css"),
                    "a { color: red; }\nb { color: blue; }\n",
                )


if __name__ == "__main__":
    unittest.main()
