"""Full Upwork workbook: official operation catalog plus live account sheets."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from upwork_client import UpworkError

CATALOG_PATH = Path(__file__).with_name("api_catalog.json")
DEFAULT_XLSX = Path.home() / "Desktop" / "upwork" / "upwork-full.xlsx"

DATA_SHEETS = [
    "Profile",
    "Companies",
    "Connects",
    "ConnectHistory",
    "Jobs",
    "Proposals",
    "Rooms",
    "Messages",
    "Contracts",
    "Transactions",
    "Activity",
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E3A")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=11)
CELL_FONT = Font(name="Arial", size=10)
TITLE_FONT = Font(name="Arial", bold=True, size=16, color="1F4E3A")
THIN = Border(
    left=Side(style="thin", color="D9E2DC"),
    right=Side(style="thin", color="D9E2DC"),
    top=Side(style="thin", color="D9E2DC"),
    bottom=Side(style="thin", color="D9E2DC"),
)

MONEY = "{ rawValue currency displayValue }"


def parse_operations(text: str) -> list[dict[str, str]]:
    marks = list(re.finditer(r"^## `([^`]+)`\s*$", text, re.M))
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, mark in enumerate(marks):
        name = mark.group(1)
        if name in seen:
            continue
        seen.add(name)
        end = marks[index + 1].start() if index + 1 < len(marks) else mark.end() + 2500
        body = text[mark.end() : end]
        desc = _section(body, "Description")
        permission = _section(body, "Required Permissions")
        kind = "mutation" if re.search(r"\bmutation\b", body[:1200]) else "query"
        found.append(
            {
                "name": name,
                "kind": kind,
                "permission": permission.replace("\n", " ")[:400],
                "description": desc.replace("\n", " ")[:500],
            }
        )
    return found


def _section(body: str, title: str) -> str:
    match = re.search(rf"##### {title}\s*\n+(.+?)(?:\n##### |\n- |\n## |\Z)", body, re.S)
    if not match:
        return ""
    return " ".join(match.group(1).split())


def load_catalog() -> list[dict[str, str]]:
    if not CATALOG_PATH.exists():
        raise UpworkError(f"Missing API catalog: {CATALOG_PATH}")
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise UpworkError("api_catalog.json must be a list")
    return data


def export_excel(api: Any, job_query: str = "", output_path: str = "") -> dict[str, Any]:
    destination = Path(output_path) if output_path else DEFAULT_XLSX
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in DATA_SHEETS}
    tables["Operations"] = load_catalog()
    coverage: list[dict[str, str]] = [
        {"sheet": "Operations", "status": "catalog", "detail": f"{len(tables['Operations'])} documented operations"}
    ]
    authorized = bool(api.status().get("authorized"))
    if not authorized:
        coverage.append({"sheet": "Live", "status": "needs_auth", "detail": "No OAuth token. Catalog only."})
    else:
        _pull_live(api, job_query, tables, coverage)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write(destination, tables, coverage)
    return {
        "path": str(destination),
        "operations": len(tables["Operations"]),
        "authorized": authorized,
        "coverage": coverage,
    }


def _pull_live(api: Any, job_query: str, tables: dict[str, list[dict[str, Any]]], coverage: list[dict[str, str]]) -> None:
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=180)).isoformat()
    date_range = {"rangeStart": start, "rangeEnd": end}

    who = _capture(coverage, "Profile", lambda: _q_who(api))
    if who:
        user = who.get("user") or {}
        org = who.get("organization") or {}
        if org.get("id"):
            api.remember_tenant(str(org["id"]))
        tables["Profile"].append(
            {
                "user_id": user.get("id", ""),
                "user_nid": user.get("nid", ""),
                "user_rid": user.get("rid", ""),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "organization_id": org.get("id", ""),
                "organization_name": org.get("name", ""),
                "organization_type": org.get("type", ""),
            }
        )
        vendor_id = str(user.get("id") or "")
    else:
        vendor_id = ""

    companies = _capture(coverage, "Companies", lambda: _q_companies(api))
    for item in ((companies or {}).get("companySelector") or {}).get("items") or []:
        tables["Companies"].append(item)

    connects = _capture(coverage, "Connects", lambda: _q_connects(api))
    summary = (connects or {}).get("connectsSummary") or {}
    if summary:
        tables["Connects"].append(summary)

    history = _capture(
        coverage,
        "ConnectHistory",
        lambda: api.graphql(
            """
            query ConnectHistory($filter: ConnectUsageFilter!, $pagination: Pagination!) {
              connectUsageHistory(filter: $filter, pagination: $pagination) {
                transactions { amount %s createdDateTime transactionType reason }
              }
            }
            """
            % MONEY,
            {"filter": {"searchDateRange": date_range}, "pagination": {"after": "", "first": 50}},
        ),
    )
    for row in ((history or {}).get("connectUsageHistory") or {}).get("transactions") or []:
        amount = row.get("amount") or {}
        tables["ConnectHistory"].append(
            {
                "created": row.get("createdDateTime", ""),
                "type": row.get("transactionType", ""),
                "reason": row.get("reason", ""),
                "amount": amount.get("rawValue", ""),
                "currency": amount.get("currency", ""),
                "display": amount.get("displayValue", ""),
            }
        )

    if job_query.strip():
        jobs = _capture(
            coverage,
            "Jobs",
            lambda: api.graphql(
                """
                query SearchJobs($filter: MarketplaceJobPostingsSearchFilter) {
                  marketplaceJobPostingsSearch(
                    marketPlaceJobFilter: $filter
                    searchType: USER_JOBS_SEARCH
                    sortAttributes: [{ field: RECENCY }]
                  ) {
                    totalCount
                    edges { node { id title description ciphertext amount { displayValue currency } } }
                  }
                }
                """,
                {"filter": {"searchExpression_eq": job_query.strip(), "pagination_eq": {"after": "0", "first": 20}}},
            ),
        )
        for edge in ((jobs or {}).get("marketplaceJobPostingsSearch") or {}).get("edges") or []:
            node = edge.get("node") or {}
            amount = node.get("amount") or {}
            tables["Jobs"].append(
                {
                    "id": node.get("id", ""),
                    "title": node.get("title", ""),
                    "ciphertext": node.get("ciphertext", ""),
                    "amount": amount.get("displayValue", ""),
                    "currency": amount.get("currency", ""),
                    "description": (node.get("description") or "")[:2000],
                }
            )
    else:
        coverage.append({"sheet": "Jobs", "status": "skipped", "detail": "Pass job_query to fill this sheet"})

    proposals = _capture(coverage, "Proposals", lambda: _q_proposals(api))
    for edge in ((proposals or {}).get("vendorProposals") or {}).get("edges") or []:
        node = edge.get("node") or {}
        job = (node.get("marketplaceJobPosting") or {}).get("content") or {}
        rate = (node.get("terms") or {}).get("chargeRate") or {}
        tables["Proposals"].append(
            {
                "id": node.get("id", ""),
                "status": (node.get("status") or {}).get("status", ""),
                "job_id": (node.get("marketplaceJobPosting") or {}).get("id", ""),
                "job_title": job.get("title", ""),
                "rate": rate.get("displayValue", ""),
            }
        )

    rooms = _capture(coverage, "Rooms", lambda: _q_rooms(api))
    room_nodes = []
    for edge in ((rooms or {}).get("roomList") or {}).get("edges") or []:
        node = edge.get("node") or {}
        room_nodes.append(node)
        tables["Rooms"].append(
            {
                "id": node.get("id", ""),
                "name": node.get("roomName", ""),
                "topic": node.get("topic", ""),
                "unread": node.get("numUnread", ""),
            }
        )

    message_rows = 0
    message_error = ""
    for room in room_nodes[:20]:
        try:
            payload = api.graphql(
                """
                query RoomMessages($filter: RoomStoryFilter!) {
                  roomStories(filter: $filter) { edges { node { id message } } }
                }
                """,
                {"filter": {"roomId_eq": room.get("id"), "storyFilter": {"pagination": {"after": "", "first": 15}}}},
            )
        except Exception as exc:  # noqa: BLE001
            message_error = str(exc)[:240]
            break
        for edge in (payload.get("roomStories") or {}).get("edges") or []:
            node = edge.get("node") or {}
            tables["Messages"].append(
                {
                    "room_id": room.get("id", ""),
                    "room_name": room.get("roomName", ""),
                    "story_id": node.get("id", ""),
                    "message": node.get("message", ""),
                }
            )
            message_rows += 1
    coverage.append(
        {
            "sheet": "Messages",
            "status": "blocked" if message_error else "ok",
            "detail": message_error or f"{message_rows} stories from {min(len(room_nodes), 20)} rooms",
        }
    )

    if vendor_id:
        contracts = _capture(
            coverage,
            "Contracts",
            lambda: api.graphql(
                """
                query VendorContracts($filter: VendorContractSearchFilter!) {
                  vendorContracts(filter: $filter) { contracts { id title status } }
                }
                """,
                {"filter": {"vendorId": vendor_id}},
            ),
        )
        for row in ((contracts or {}).get("vendorContracts") or {}).get("contracts") or []:
            tables["Contracts"].append(
                {"id": row.get("id", ""), "title": row.get("title", ""), "status": str(row.get("status", ""))}
            )
    else:
        coverage.append({"sheet": "Contracts", "status": "blocked", "detail": "Profile did not return a user id"})

    entity = _capture(coverage, "Accounting", lambda: _q_accounting(api))
    ace_id = ((entity or {}).get("accountingEntity") or {}).get("id")
    if ace_id:
        tx = _capture(
            coverage,
            "Transactions",
            lambda: api.graphql(
                """
                query Tx($filter: TransactionHistoryFilter) {
                  transactionHistory(transactionHistoryFilter: $filter) {
                    transactionDetail {
                      transactionHistoryRow {
                        recordId type description descriptionUI transactionCreationDate
                        paymentStatus remainder
                        transactionAmount %s
                      }
                    }
                  }
                }
                """
                % MONEY,
                {"filter": {"aceIds_any": [ace_id], "transactionDateTime_bt": date_range}},
            ),
        )
        rows = (((tx or {}).get("transactionHistory") or {}).get("transactionDetail") or {}).get("transactionHistoryRow") or []
        for row in rows:
            amount = row.get("transactionAmount") or {}
            tables["Transactions"].append(
                {
                    "record_id": row.get("recordId", ""),
                    "type": row.get("type", ""),
                    "created": row.get("transactionCreationDate", ""),
                    "description": row.get("descriptionUI") or row.get("description") or "",
                    "amount": amount.get("rawValue", ""),
                    "currency": amount.get("currency", ""),
                    "display": amount.get("displayValue", ""),
                    "payment_status": row.get("paymentStatus", ""),
                }
            )
    else:
        coverage.append({"sheet": "Transactions", "status": "blocked", "detail": "No accounting entity id"})

    activity = _capture(
        coverage,
        "Activity",
        lambda: api.graphql(
            """
            query Activity($filter: ProfileActivityMetricsFilter!) {
              profileActivityMetrics(filter: $filter) {
                metrics { metric data { timestamp count } }
              }
            }
            """,
            {
                "filter": {
                    "metrics": ["PROFILE_VIEWS", "INVITES", "PROPOSALS_SENT", "PROPOSALS_HIRED"],
                    "dateRange": date_range,
                    "step": "WEEK",
                }
            },
        ),
    )
    for metric in ((activity or {}).get("profileActivityMetrics") or {}).get("metrics") or []:
        for point in metric.get("data") or []:
            tables["Activity"].append(
                {"metric": metric.get("metric", ""), "timestamp": point.get("timestamp", ""), "count": point.get("count", 0)}
            )


def _q_who(api: Any) -> dict[str, Any]:
    return api.graphql("query Who { user { id nid rid email name } organization { id name type } }")


def _q_companies(api: Any) -> dict[str, Any]:
    return api.graphql(
        """
        query Companies {
          companySelector {
            items { title organizationId organizationRid organizationType organizationLegacyType typeTitle }
          }
        }
        """
    )


def _q_connects(api: Any) -> dict[str, Any]:
    return api.graphql(
        """
        query Connects {
          connectsSummary {
            organizationId connectsBalance rolloverBalance connectsBalanceFree connectsBalancePaid
          }
        }
        """
    )


def _q_proposals(api: Any) -> dict[str, Any]:
    return api.graphql(
        """
        query Proposals($filter: VendorProposalFilter!, $sortAttribute: VendorProposalSortAttribute!, $pagination: Pagination!) {
          vendorProposals(filter: $filter, sortAttribute: $sortAttribute, pagination: $pagination) {
            totalCount
            edges { node { id status { status } marketplaceJobPosting { id content { title } } terms { chargeRate { displayValue } } } }
          }
        }
        """,
        {
            "filter": {},
            "sortAttribute": {"field": "CREATEDDATETIME", "sortOrder": "DESC"},
            "pagination": {"after": None, "first": 50},
        },
    )


def _q_rooms(api: Any) -> dict[str, Any]:
    return api.graphql(
        """
        query Rooms($filter: RoomFilter, $pagination: Pagination) {
          roomList(filter: $filter, pagination: $pagination, sortOrder: DESC) {
            totalCount
            edges { node { id roomName topic numUnread } }
          }
        }
        """,
        {"filter": {"subscribed_eq": True}, "pagination": {"after": "", "first": 30}},
    )


def _q_accounting(api: Any) -> dict[str, Any]:
    return api.graphql("query Ace { accountingEntity { id } }")


def _capture(coverage: list[dict[str, str]], sheet: str, call) -> dict[str, Any] | None:
    try:
        data = call()
    except Exception as exc:  # noqa: BLE001
        coverage.append({"sheet": sheet, "status": "blocked", "detail": str(exc)[:300]})
        return None
    coverage.append({"sheet": sheet, "status": "ok", "detail": "pulled"})
    return data


def _write(path: Path, tables: dict[str, list[dict[str, Any]]], coverage: list[dict[str, str]]) -> None:
    book = Workbook()
    summary = book.active
    summary.title = "Summary"
    _style_title(summary)
    headers = _union_headers(tables)
    order = ["Operations", *DATA_SHEETS]
    for name in order:
        sheet = book.create_sheet(name)
        _write_table(sheet, headers[name], tables.get(name) or [])
    cover = book.create_sheet("Coverage")
    _write_table(cover, ["sheet", "status", "detail"], coverage)
    _write_summary(summary, order)
    book.save(path)


def _union_headers(tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    headers: dict[str, list[str]] = {}
    for name, rows in tables.items():
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(str(key))
        headers[name] = keys or ["id"]
    return headers


def _style_title(sheet: Worksheet) -> None:
    sheet["A1"] = "Upwork"
    sheet["A1"].font = TITLE_FONT
    sheet["A2"] = "Catalog source: Upwork GraphQL documentation snapshot 2026-11-25. Live rows need an OAuth token."
    sheet["A2"].font = CELL_FONT
    sheet.merge_cells("A2:C2")


def _write_summary(sheet: Worksheet, names: list[str]) -> None:
    labels = ["Sheet", "Rows", "Status"]
    for col, label in enumerate(labels, start=1):
        cell = sheet.cell(4, col, label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for index, name in enumerate(names):
        row = 5 + index
        sheet.cell(row, 1, name).font = CELL_FONT
        sheet.cell(row, 2, f"=MAX(0,COUNTA('{name}'!A:A)-1)").font = CELL_FONT
        sheet.cell(row, 3, f'=IFERROR(INDEX(Coverage!B:B,MATCH(A{row},Coverage!A:A,0)),"")').font = CELL_FONT
        for col in range(1, 4):
            sheet.cell(row, col).border = THIN
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 12
    sheet.column_dimensions["C"].width = 36
    sheet.auto_filter.ref = f"A4:C{4 + len(names)}"
    sheet.freeze_panes = "A5"
    sheet.sheet_view.showGridLines = False


def _write_table(sheet: Worksheet, headers: list[str], rows: list[dict[str, Any]]) -> None:
    for col, header in enumerate(headers, start=1):
        cell = sheet.cell(1, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center")
    for row_index, row in enumerate(rows, start=2):
        for col, header in enumerate(headers, start=1):
            value = row.get(header, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            cell = sheet.cell(row_index, col, value)
            cell.font = CELL_FONT
            cell.border = THIN
            cell.alignment = Alignment(vertical="top", wrap_text=(header in {"description", "message", "detail"}))
    for col, header in enumerate(headers, start=1):
        width = min(42, max(12, len(header) + 2))
        sheet.column_dimensions[get_column_letter(col)].width = width
    if headers:
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, len(rows) + 1)}"
    sheet.freeze_panes = "A2"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_view.showGridLines = False
    sheet.oddHeader.left.text = "Upwork"
    sheet.oddFooter.right.text = "Page &P"
