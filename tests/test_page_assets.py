"""The page's CSS and JS are files under page/, and the module inlines them.

F1 of the 8 October 2026 agent-efficiency audit: the station page's JavaScript
was 2,900 lines inside a Python string, where no editor, linter or search could
see it and no syntax check reached it, and half of every page fix landed in the
file that held it. The blocks are files now, read at import. These tests hold
what the move depends on: each file is the bytes the page ships, and a checkout
that hands back CRLF cannot rewrite every page of a release.
"""

import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from trainbudget.build import page_templates

#: Each file under page/, and the string the page ships it in. A file that is
#: not in its holder is a block that stopped being read, which leaves the page
#: unstyled or unwired rather than failing anywhere near the edit. The two
#: routes' scripts ship as one hashed asset each rather than inline, so the
#: station panels and the chooser's file are mapped to the asset the build
#: writes, with their shared blocks filled in exactly as page_templates does.
ASSETS = {
    "shared.css": "SHARED_CSS",
    "station.css": "STATION_CSS",
    "chooser.css": "_CHOOSER_TEMPLATE",
    "privacy.css": "_PRIVACY_TEMPLATE",
    "theme.js": "SHARED_THEME",
}
STATION_SCRIPT_PARTS = {
    "station/payload.js": "STATION_SCRIPT",
    "station/state.js": "STATION_SCRIPT",
    "station/railcards.js": "STATION_SCRIPT",
    "station/budget.js": "STATION_SCRIPT",
    "station/service-day.js": "STATION_SCRIPT",
    "station/filters.js": "STATION_SCRIPT",
    "station/ticket-modes.js": "STATION_SCRIPT",
    "station/format.js": "STATION_SCRIPT",
    "station/table.js": "STATION_SCRIPT",
    "station/row-cells.js": "STATION_SCRIPT",
    "station/fare-panel.js": "STATION_SCRIPT",
    "station/row-actions.js": "STATION_SCRIPT",
    "station/provenance.js": "STATION_SCRIPT",
    "station/picker.js": "STATION_SCRIPT",
    "station/shortlist.js": "STATION_SCRIPT",
    "station/url-state.js": "STATION_SCRIPT",
    "station/wiring.js": "STATION_SCRIPT",
    "chooser.js": "CHOOSER_SCRIPT",
}


class PageAssetTest(unittest.TestCase):
    def test_every_asset_is_a_file_that_lands_in_the_page(self) -> None:
        for asset, holder in {**ASSETS, **STATION_SCRIPT_PARTS}.items():
            with self.subTest(asset=asset):
                self.assertTrue(
                    Path(page_templates._PAGE_ASSETS, asset).is_file(),
                    f"page/{asset} is missing from the module's own directory",
                )
                text = page_templates._page_file(asset)
                self.assertGreater(len(text.strip()), 0, f"page/{asset} is empty")
                if holder in ("STATION_SCRIPT", "CHOOSER_SCRIPT"):
                    # The asset carries the file with the shared blocks filled
                    # in, so the raw bytes are not what is asserted: the
                    # filled text is, which is what the browser executes.
                    filled = page_templates._shared_script(text, asset)
                    self.assertIn(
                        filled,
                        getattr(page_templates, holder),
                        f"page/{asset} is not the block {holder} holds",
                    )
                else:
                    self.assertIn(
                        text,
                        getattr(page_templates, holder),
                        f"page/{asset} is not the block {holder} holds",
                    )

    def test_the_shared_assets_hold_every_part_and_nothing_else(self) -> None:
        # A panel dropped from the concatenation order would still be a file
        # the test above finds, so the assets are also proved whole: each one
        # is exactly its parts, filled, in order.
        station = "".join(
            page_templates._shared_script(
                page_templates._page_file(part), part
            )
            for part in page_templates.STATION_SCRIPT_PARTS
        )
        self.assertEqual(page_templates.STATION_SCRIPT, station)
        chooser = page_templates._shared_script(
            page_templates._page_file("chooser.js"), "chooser.js"
        )
        self.assertEqual(page_templates.CHOOSER_SCRIPT, chooser)

    def test_no_shared_asset_declares_a_per_page_value(self) -> None:
        # One shared file cannot carry a page's destinations or a build's
        # station list: those arrive on window.TBE_* from the small block each
        # page inlines, and a placeholder left here would ship a literal
        # __NAME__ to the browser on every page of the route.
        for name in ("STATION_SCRIPT", "CHOOSER_SCRIPT"):
            with self.subTest(asset=name):
                asset = getattr(page_templates, name)
                for placeholder in (
                    "__DATA__",
                    "__FIRST_USE_FALLBACK__",
                    "__STATIONS__",
                    "__TITLE_SUFFIX_JS__",
                    "__LIST_KEYS__",
                    "__STATION_MATCH__",
                    "__STATION_FIELD__",
                    "__CHEVRON_JS__",
                ):
                    self.assertNotIn(
                        placeholder, asset, f"{name} still holds {placeholder}"
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
        self.assertEqual(on_disk, set({**ASSETS, **STATION_SCRIPT_PARTS}))

    def test_no_asset_carries_a_carriage_return(self) -> None:
        # The built page's bytes are the template's bytes, and the templates use
        # LF. A file that gained a CR would change every page that inlines it.
        for asset in {**ASSETS, **STATION_SCRIPT_PARTS}:
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


    def test_each_template_names_its_payload_with_the_marker_it_declares(self) -> None:
        # The template is where the line is written, so the constant and the
        # literal are one fact stated twice. Held together here because the
        # failure is silent: eight spellings of this marker existed on 18 October
        # 2026, the renderer had moved past one of them, and the byte measurer
        # went on reading a marker no page wrote. It reported every page as
        # carrying 0 KB of payload and the budget gate passed.
        self.assertIn(page_templates.PAYLOAD_MARKER, page_templates.TEMPLATE)
        self.assertIn(page_templates.CHOOSER_MARKER, page_templates._CHOOSER_TEMPLATE)

    def test_every_reader_of_the_marker_derives_it_from_the_template(self) -> None:
        # A reader that spells the marker again is a copy, and a copy is what
        # went stale. These two are the readers that measure and gate a built
        # page, so they are the ones whose drift would pass a check.
        from tools import check_source_credit, page_bytes

        self.assertEqual(check_source_credit.FARE_MARK, page_templates.PAYLOAD_MARKER)
        self.assertEqual(
            page_bytes.INLINE_JSON_MARKERS,
            (page_templates.PAYLOAD_MARKER, page_templates.CHOOSER_MARKER),
        )


#: A function the script declares on its own, at the top level, where every
#: later panel can call it.
SHARED_FUNCTION = re.compile(
    r"^(?:function\s+(\w+)\s*\(|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?(?:function\b|\())"
)
#: A declaration indented inside a function, which shadows a top-level name.
LOCAL_DECLARATION = re.compile(r"\s+(?:const|let|var)\s+(\w+)\s*=")
TOP_LEVEL_DECLARATION = re.compile(r"^(?:const|let|var|function)\s+(\w+)")
#: One top-level constant that is only another name for a binding beside it.
ALIAS = re.compile(r"^const (\w+) = (\w+);$")


def script_sources() -> dict[str, str]:
    """Every file the routes' scripts are built from, by its own name."""
    return {
        path.relative_to(page_templates._PAGE_ASSETS).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(page_templates._PAGE_ASSETS.rglob("*.js"))
    }


def shared_field_calls(source: str) -> list[str]:
    """The text of each ``attachStationField({...})`` call, braces paired."""
    calls = []
    for match in re.finditer(r"attachStationField\(\{", source):
        start = source.index("{", match.start())
        depth, index = 0, start
        while index < len(source):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    calls.append(source[start : index + 1])
                    break
            index += 1
    return calls


class PageScriptSurfaceTest(unittest.TestCase):
    """The page's script is one file, so its top level is one shared namespace.

    Each check is a fault the 17 October 2026 audit found by reading the panels
    (E18): a local that shadows a helper, a constant that only renames another,
    and an option the shared station field reads that no caller passes. The
    third instance of the first fault, a local ``unit`` in url-state.js, was
    found by writing this class rather than by the audit.
    """

    def test_no_local_declaration_shadows_a_shared_function(self) -> None:
        sources = script_sources()
        functions: dict[str, str] = {}
        for name, source in sources.items():
            for number, line in enumerate(source.splitlines(), 1):
                match = SHARED_FUNCTION.match(line)
                if match:
                    functions[match.group(1) or match.group(2)] = f"page/{name}:{number}"
        shadows = []
        for name, source in sources.items():
            for number, line in enumerate(source.splitlines(), 1):
                match = LOCAL_DECLARATION.match(line)
                if match and match.group(1) in functions:
                    shadows.append(
                        f"page/{name}:{number} declares {match.group(1)}, "
                        f"which {functions[match.group(1)]} defines"
                    )
        self.assertEqual(shadows, [])

    def test_no_top_level_constant_only_renames_another(self) -> None:
        sources = script_sources()
        declared = {
            match.group(1)
            for source in sources.values()
            for line in source.splitlines()
            if (match := TOP_LEVEL_DECLARATION.match(line))
        }
        aliases = []
        for name, source in sources.items():
            for number, line in enumerate(source.splitlines(), 1):
                match = ALIAS.match(line)
                if match and match.group(2) in declared and match.group(1) != match.group(2):
                    aliases.append(
                        f"page/{name}:{number} defines {match.group(1)} as {match.group(2)}"
                    )
        self.assertEqual(aliases, [])

    def test_every_option_the_shared_field_reads_is_passed_by_a_caller(self) -> None:
        read = set(re.findall(r"options\.(\w+)", page_templates.STATION_FIELD_JS))
        passed = set()
        for source in script_sources().values():
            for call in shared_field_calls(source):
                passed.update(re.findall(r"^\s+(\w+):", call, re.M))
        self.assertEqual(
            sorted(read - passed), [],
            "the shared station field reads an option no caller passes",
        )


if __name__ == "__main__":
    unittest.main()
