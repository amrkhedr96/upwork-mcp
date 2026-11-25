import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from workbook import export_excel, parse_operations


SAMPLE = """
## `connectsSummary`

##### Description

Fetch connects summary

##### Required Permissions

"Ad Credits and Connects Information - Read-Only Access"

query connectsSummary { connectsSummary { connectsBalance } }

## `createJobProposal`

##### Description

Create a new proposal

##### Required Permissions

"Submit Proposal"

mutation createJobProposal { createJobProposal { status } }
"""


class FakeApi:
    def __init__(self, authorized: bool, payload: dict | None = None) -> None:
        self.authorized = authorized
        self.payload = payload or {}
        self.tenant = ""

    def status(self) -> dict:
        return {"authorized": self.authorized}

    def remember_tenant(self, tenant_id: str) -> None:
        self.tenant = tenant_id

    def graphql(self, query: str, variables=None) -> dict:
        for key, value in self.payload.items():
            if key in query:
                return value
        raise RuntimeError(f"no fixture for query: {query[:80]}")


class WorkbookTests(unittest.TestCase):
    def test_parser_keeps_query_and_mutation(self) -> None:
        ops = parse_operations(SAMPLE)
        self.assertEqual([item["name"] for item in ops], ["connectsSummary", "createJobProposal"])
        self.assertEqual(ops[1]["kind"], "mutation")
        self.assertIn("Submit Proposal", ops[1]["permission"])

    def test_export_writes_catalog_and_formulas_without_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "upwork-full.xlsx"
            result = export_excel(FakeApi(False), output_path=str(target))
            self.assertGreater(result["operations"], 50)
            self.assertFalse(result["authorized"])
            book = load_workbook(target)
            self.assertIn("Operations", book.sheetnames)
            self.assertIn("Transactions", book.sheetnames)
            self.assertTrue(str(book["Summary"]["B5"].value).startswith("=MAX"))
            names = [book["Operations"].cell(row, 1).value for row in range(2, book["Operations"].max_row + 1)]
            self.assertIn("connectsSummary", names)
            self.assertIn("createJobProposal", names)


if __name__ == "__main__":
    unittest.main()
