"""The licence register must stay true to the shelf of PDFs beside it.

A licence that is downloaded, filed and forgotten is the failure this test exists to
prevent. Every product licence PDF in `licences/` must have a row in
`licences/README.md`, and every row must point at a file that is really there, so
the two cannot drift apart as more products are subscribed to (ADR-0021).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

LICENCES = Path(__file__).parent / "licences"
REGISTER = LICENCES / "README.md"

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
)


class LicenceRegisterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.register = REGISTER.read_text(encoding="utf-8")
        self.pdfs = sorted(p for p in LICENCES.glob("*.pdf") if p.name not in SUPPORTING)
        # Rows of the register's product table, which are the ones carrying a product id.
        self.rows = [
            line
            for line in self.register.splitlines()
            if line.startswith("|") and PRODUCT_ID.search(line)
        ]

    def test_there_is_a_licence_to_read(self) -> None:
        self.assertTrue(self.pdfs, f"no licence PDFs in {LICENCES}")

    def test_every_filed_pdf_is_named_for_a_registered_product(self) -> None:
        # The register maps id to row and the filename carries that id, which is the
        # pair the marketplace issues ("<product name>-...-P-<id>.pdf"), so a filed
        # licence is traceable to its row even though the filename is never quoted.
        for pdf in self.pdfs:
            with self.subTest(pdf=pdf.name):
                found = PRODUCT_ID.search(pdf.name)
                self.assertIsNotNone(found, f"{pdf.name} carries no product id")
                self.assertIn(found.group(0), self.register, f"{pdf.name} is filed but not registered")

    def test_every_product_id_is_registered_and_present(self) -> None:
        ids = {PRODUCT_ID.search(pdf.name).group(0) for pdf in self.pdfs}
        for product_id in ids:
            with self.subTest(product=product_id):
                self.assertIn(product_id, self.register)
        for row in self.rows:
            for product_id in PRODUCT_ID.findall(row):
                with self.subTest(product=product_id):
                    self.assertIn(
                        product_id,
                        ids,
                        f"{product_id} is registered but no licence PDF is filed for it",
                    )

    def test_every_row_records_the_verdict_that_decides_publication(self) -> None:
        self.assertEqual(len(self.rows), len(self.pdfs), "one row per product, no orphans")
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
