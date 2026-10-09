"""The licence register must stay true to the committed shelf.

A licence that is downloaded, filed and forgotten is the failure this test exists to
prevent. Every marketplace product in `licences/licence-manifest.json` must have a
row in `licences/README.md`, and every row must name a product the manifest
carries (ADR-0021, ADR-0067). The PDFs are not in git. When they are on disk,
each one must match the manifest's SHA-256, and a PDF the manifest does not
name fails the same way a forgotten file always has.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

LICENCES = Path(__file__).parent.parent / "licences"
REGISTER = LICENCES / "README.md"
MANIFEST = LICENCES / "licence-manifest.json"

# The product id the marketplace puts in the licence filename and in Schedule 1 §3.
PRODUCT_ID = re.compile(r"P-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# The one field that decides whether a product may appear on a public page. A row
# that does not state it has not been read (ADR-0021).
VERDICTS = ("internal only", "distribute")

# How a row may describe the money. "nil" for the Open products, "free" for the
# Bespoke one that is free within a non-chargeable limit, "not held" for a product
# still to be obtained (ADR-0022).
FEE_OUTCOMES = ("nil", "free", "no charge", "not held")

# Supporting documents kept as evidence but issued by nobody and licensing nothing:
# price schedules, specifications. They carry no product id, and the register lists
# them outside the product table (ADR-0022).
# These are source documents, not per-product Marketplace licences, so they do
# not carry a product id or occupy a row in the product table.
SUPPORTING = (
    "BR Fares RDM Pricing.pdf",
    "National Rail Data Portal Terms-and-conditions.pdf",
    "NRE Developer Brand Guidelines September 2026.pdf",
    "NRE Feeds Developer Pack v.01-05.pdf",
)


class LicenceRegisterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.register = REGISTER.read_text(encoding="utf-8")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
        self.product_rows = [row for row in self.manifest if row.get("product_id")]
        self.pdfs = [LICENCES / row["filename"] for row in self.product_rows]
        # Rows of the register's product table, which are the ones carrying a product id.
        self.rows = [
            line
            for line in self.register.splitlines()
            if line.startswith("|") and PRODUCT_ID.search(line)
        ]

    def test_there_is_a_licence_to_read(self) -> None:
        self.assertTrue(self.product_rows, f"no product licences in {MANIFEST}")

    def test_every_manifest_product_is_registered(self) -> None:
        # The register maps id to row and the filename carries that id, which is the
        # pair the marketplace issues ("<product name>-...-P-<id>.pdf"), so a filed
        # licence is traceable to its row even though the filename is never quoted.
        for row in self.product_rows:
            with self.subTest(pdf=row["filename"]):
                self.assertIsNotNone(PRODUCT_ID.fullmatch(row["product_id"]))
                self.assertIn(row["product_id"], row["filename"])
                self.assertIn(
                    row["product_id"],
                    self.register,
                    f"{row['filename']} is on the manifest but not registered",
                )

    def test_every_product_id_is_registered_and_on_the_manifest(self) -> None:
        ids = {row["product_id"] for row in self.product_rows}
        for product_id in ids:
            with self.subTest(product=product_id):
                self.assertIn(product_id, self.register)
        for row in self.rows:
            for product_id in PRODUCT_ID.findall(row):
                with self.subTest(product=product_id):
                    self.assertIn(
                        product_id,
                        ids,
                        f"{product_id} is registered but the manifest has no licence for it",
                    )

    def test_a_pdf_on_disk_matches_the_manifest_or_is_named_by_it(self) -> None:
        # Local copies are the evidence. CI has none, and that is allowed.
        # A copy that is here and does not match, or a copy the manifest does
        # not name, is a licence the gate has not been told about.
        by_name = {row["filename"]: row["sha256"] for row in self.manifest}
        for filename, sha in by_name.items():
            path = LICENCES / filename
            if not path.is_file():
                continue
            with self.subTest(pdf=filename):
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(actual, sha, f"{filename} does not match the manifest")
        for path in sorted(LICENCES.glob("*.pdf")):
            with self.subTest(pdf=path.name):
                self.assertIn(path.name, by_name, f"{path.name} is not in the manifest")
                if path.name not in SUPPORTING:
                    self.assertIsNotNone(PRODUCT_ID.search(path.name))

    def test_every_row_records_the_verdict_that_decides_publication(self) -> None:
        self.assertEqual(len(self.rows), len(self.product_rows), "one row per product, no orphans")
        for row in self.rows:
            with self.subTest(row=row[:60]):
                self.assertTrue(
                    any(verdict in row for verdict in VERDICTS),
                    "the row does not say whether Schedule 1 §5 permits publication",
                )

    def test_every_row_states_the_fee_outcome(self) -> None:
        for row in self.rows:
            with self.subTest(row=row[:60]):
                self.assertTrue(
                    any(outcome in row for outcome in FEE_OUTCOMES),
                    "the row does not say what the licence costs",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
