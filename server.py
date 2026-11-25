"""Upwork MCP. Reads the official GraphQL API. Sends nothing unless confirm=true."""

from __future__ import annotations

import json
from functools import wraps
from typing import Any

from mcp.server.fastmcp import FastMCP

from upwork_client import UpworkClient, UpworkError, proposal_input

mcp = FastMCP("upwork_mcp")
_client: UpworkClient | None = None

SEARCH_JOBS = """
query SearchJobs($filter: MarketplaceJobPostingsSearchFilter) {
  marketplaceJobPostingsSearch(
    marketPlaceJobFilter: $filter
    searchType: USER_JOBS_SEARCH
    sortAttributes: [{ field: RECENCY }]
  ) {
    totalCount
    edges {
      node {
        id
        title
        description
        ciphertext
        amount { displayValue currency }
        skills { name }
        client { totalFeedback }
      }
    }
  }
}
"""

JOB_CONTENT = """
query JobContent($ids: [ID!]!) {
  marketplaceJobPostingsContents(ids: $ids) {
    id
    ciphertext
    title
    description
    publishedDateTime
  }
}
"""

WHOAMI = """
query WhoAmI {
  user { id nid rid email name }
  organization { id name type }
}
"""

LIST_PROPOSALS = """
query FreelancerVendorProposals(
  $filter: VendorProposalFilter!
  $sortAttribute: VendorProposalSortAttribute!
  $pagination: Pagination!
) {
  vendorProposals(
    filter: $filter
    sortAttribute: $sortAttribute
    pagination: $pagination
  ) {
    totalCount
    edges {
      node {
        id
        status { status }
        marketplaceJobPosting { id content { title } }
        terms { chargeRate { displayValue } }
      }
    }
  }
}
"""

GET_PROPOSAL = """
query OneProposal($id: ID!) {
  vendorProposal(id: $id) {
    id
    coverLetter
    proposalCoverLetter
    viewedByClient
    status { status }
    terms { chargeRate { displayValue } }
    marketplaceJobPosting { id content { title } }
  }
}
"""

LIST_ROOMS = """
query ListRooms($filter: RoomFilter, $pagination: Pagination) {
  roomList(filter: $filter, pagination: $pagination, sortOrder: DESC) {
    totalCount
    edges { node { id roomName topic numUnread } }
  }
}
"""

ROOM_MESSAGES = """
query RoomMessages($filter: RoomStoryFilter!) {
  roomStories(filter: $filter) {
    edges { node { id message } }
  }
}
"""

SEND_MESSAGE = """
mutation Send($input: RoomStoryCreateInputV2!) {
  createRoomStoryV2(input: $input) { id createdDateTime }
}
"""

SUBMIT_PROPOSAL = """
mutation createJobProposal($input: CreateJobProposalInput!) {
  createJobProposal(input: $input) {
    newProposalId
    status
    error
  }
}
"""

LIST_CONTRACTS = """
query VendorContracts($filter: VendorContractSearchFilter!) {
  vendorContracts(filter: $filter) {
    contracts { id title status }
  }
}
"""


def client() -> UpworkClient:
    global _client
    if _client is None:
        _client = UpworkClient()
    return _client


def dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def safe(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except UpworkError as exc:
            return dump({"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001 — surface API/transport failures to the agent
            return dump({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    return wrapped


@mcp.tool()
@safe
def upwork_status() -> str:
    """Show whether API credentials and an OAuth token exist. Never returns the secret."""
    return dump(client().status())


@mcp.tool()
@safe
def upwork_save_credentials(client_id: str, client_secret: str, redirect_uri: str = "") -> str:
    """Save the OAuth client id, secret, and callback URL on this machine. Does not echo the secret."""
    client().store.save_config(client_id, client_secret, redirect_uri)
    status = client().status()
    status["saved"] = True
    return dump(status)


@mcp.tool()
@safe
def upwork_auth_url() -> str:
    """Build the Upwork OAuth approval URL. The user opens it and copies the code query parameter."""
    return dump({"url": client().begin_auth()})


@mcp.tool()
@safe
def upwork_exchange_code(code: str) -> str:
    """Exchange the one-time OAuth code for a local access token."""
    return dump(client().exchange_code(code))


@mcp.tool()
@safe
def upwork_whoami() -> str:
    """Read the signed-in user and organization. Stores the organization id for later API calls."""
    data = client().graphql(WHOAMI)
    org = data.get("organization") or {}
    if org.get("id"):
        client().remember_tenant(str(org["id"]))
    return dump(data)


@mcp.tool()
@safe
def upwork_search_jobs(query: str, first: int = 10) -> str:
    """Search marketplace jobs. Requires the Read marketplace Job Postings scope."""
    first = max(1, min(first, 20))
    data = client().graphql(
        SEARCH_JOBS,
        {
            "filter": {
                "searchExpression_eq": query,
                "pagination_eq": {"after": "0", "first": first},
            }
        },
    )
    return dump(data)


@mcp.tool()
@safe
def upwork_job(job_id: str) -> str:
    """Read one marketplace job by id."""
    return dump(client().graphql(JOB_CONTENT, {"ids": [job_id]}))


@mcp.tool()
@safe
def upwork_list_proposals(status: str = "", first: int = 20) -> str:
    """List this freelancer's proposals. Optional status such as Accepted."""
    filt: dict[str, Any] = {}
    if status.strip():
        filt["status_eq"] = status.strip()
    data = client().graphql(
        LIST_PROPOSALS,
        {
            "filter": filt,
            "sortAttribute": {"field": "CREATEDDATETIME", "sortOrder": "DESC"},
            "pagination": {"after": None, "first": max(1, min(first, 50))},
        },
    )
    return dump(data)


@mcp.tool()
@safe
def upwork_proposal(proposal_id: str) -> str:
    """Read one proposal, including the cover letter."""
    return dump(client().graphql(GET_PROPOSAL, {"id": proposal_id}))


@mcp.tool()
@safe
def upwork_list_rooms(first: int = 15) -> str:
    """List subscribed message rooms."""
    data = client().graphql(
        LIST_ROOMS,
        {"filter": {"subscribed_eq": True}, "pagination": {"after": "", "first": max(1, min(first, 30))}},
    )
    return dump(data)


@mcp.tool()
@safe
def upwork_room_messages(room_id: str, first: int = 20) -> str:
    """Read recent messages in one room."""
    data = client().graphql(
        ROOM_MESSAGES,
        {"filter": {"roomId_eq": room_id, "storyFilter": {"pagination": {"after": "", "first": first}}}},
    )
    return dump(data)


@mcp.tool()
@safe
def upwork_list_contracts(vendor_id: str) -> str:
    """List contracts for a vendor id taken from upwork_whoami."""
    return dump(client().graphql(LIST_CONTRACTS, {"filter": {"vendorId": vendor_id}}))


@mcp.tool()
@safe
def upwork_send_message(room_id: str, message: str, confirm: bool = False) -> str:
    """Send a room message only when confirm is true. Otherwise return a preview."""
    preview = {"roomId": room_id, "message": message}
    if not confirm:
        return dump({"sent": False, "preview": preview})
    if not message.strip():
        raise UpworkError("message is empty")
    data = client().graphql(SEND_MESSAGE, {"input": preview})
    return dump({"sent": True, "result": data})


@mcp.tool()
@safe
def upwork_submit_proposal(
    job_reference: str,
    cover_letter: str,
    charged_amount: float,
    contractor_id: str,
    odesk_user_id: str,
    team_org_id: str,
    estimated_duration: int = 0,
    confirm: bool = False,
) -> str:
    """Submit a proposal only when confirm is true. Uses Connects. Preview otherwise."""
    body = proposal_input(
        job_reference=job_reference,
        cover_letter=cover_letter,
        charged_amount=charged_amount,
        contractor_id=contractor_id,
        odesk_user_id=odesk_user_id,
        team_org_id=team_org_id,
        estimated_duration=estimated_duration or None,
    )
    if not confirm:
        return dump({"sent": False, "preview": body, "note": "Connects are spent only after confirm=true"})
    data = client().graphql(SUBMIT_PROPOSAL, {"input": body})
    return dump({"sent": True, "result": data})


@mcp.tool()
@safe
def upwork_export_excel(job_query: str = "", output_path: str = "") -> str:
    """Write the full Upwork workbook: documented operations plus live account sheets."""
    from workbook import export_excel

    return dump(export_excel(client(), job_query, output_path))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
