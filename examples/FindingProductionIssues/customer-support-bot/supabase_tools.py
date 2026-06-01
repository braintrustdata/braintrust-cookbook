"""Supabase-backed tool implementations for the customer support chatbot.

Read tools hit the Supabase REST API (PostgREST).
Action tools call Supabase Edge Functions.

All calls are real HTTP requests — failures are genuine, not simulated.

KNOWN ISSUE: Action tools (process_refund, initiate_return, check_shipping_status)
do not retry on transient errors (5xx). If the payment processor times out or the
carrier API is temporarily down, the error is passed straight to the LLM, which
tells the customer "something went wrong" — even though a simple retry would
likely succeed. Add retry logic to _call_edge_function() to fix this.
"""

import os
import time
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://efawqblywqlirhstfdct.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ── Read tools (Supabase REST / PostgREST) ──────────────────────────────────

def lookup_order(order_id: str) -> dict | None:
    """Look up an order by ID via Supabase REST."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/orders",
        headers={**_REST_HEADERS, "Accept": "application/vnd.pgrst.object+json"},
        params={"id": f"eq.{order_id}", "select": "*"},
        timeout=10,
    )
    if resp.status_code == 406 or resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def lookup_customer_by_email(email: str) -> dict | None:
    """Find a customer by email via Supabase REST."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/customers",
        headers={**_REST_HEADERS, "Accept": "application/vnd.pgrst.object+json"},
        params={"email": f"eq.{email}", "select": "*"},
        timeout=10,
    )
    if resp.status_code == 406 or resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def lookup_customer_orders(customer_id: str) -> list[dict]:
    """Get all orders for a customer via Supabase REST."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/orders",
        headers=_REST_HEADERS,
        params={"customer_id": f"eq.{customer_id}", "select": "*", "order": "placed_at.desc"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def lookup_product(sku: str) -> dict | None:
    """Look up a product by SKU via Supabase REST."""
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/products",
        headers={**_REST_HEADERS, "Accept": "application/vnd.pgrst.object+json"},
        params={"sku": f"eq.{sku}", "select": "*"},
        timeout=10,
    )
    if resp.status_code == 406 or resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def check_return_eligibility(order_id: str) -> dict:
    """Check if an order is eligible for return via Supabase REST."""
    order = lookup_order(order_id)
    if not order:
        return {"eligible": False, "reason": "Order not found."}
    if order.get("status") == "cancelled":
        return {"eligible": False, "reason": "Order was already cancelled."}
    if order.get("status") == "return_in_progress":
        return {"eligible": False, "reason": "A return is already in progress for this order."}
    if not order.get("delivered_at"):
        return {"eligible": False, "reason": "Order has not been delivered yet."}

    from datetime import datetime
    delivered = datetime.strptime(order["delivered_at"], "%Y-%m-%d")
    days_since = (datetime.now() - delivered).days
    if days_since > 30:
        return {
            "eligible": False,
            "reason": f"Outside the 30-day return window ({days_since} days since delivery).",
            "days_since_delivery": days_since,
        }
    return {"eligible": True, "days_remaining": 30 - days_since}


# ── Action tools (Supabase Edge Functions) ───────────────────────────────────

# Set to True to enable retry logic for transient errors (5xx).
# When False (default), a single gateway timeout or service-unavailable
# response is passed straight to the LLM, which tells the customer
# "something went wrong" — even though a retry would likely succeed.
RETRY_TRANSIENT_ERRORS = False


def _call_edge_function(function_name: str, payload: dict) -> dict:
    """Call a Supabase Edge Function and return the result.

    If RETRY_TRANSIENT_ERRORS is True, retries 5xx responses up to 2 times
    with exponential backoff. 4xx errors (client errors like expired cards
    or invalid orders) are never retried — those are permanent.
    """
    url = f"{SUPABASE_URL}/functions/v1/{function_name}"
    max_attempts = 3 if RETRY_TRANSIENT_ERRORS else 1

    for attempt in range(max_attempts):
        resp = requests.post(url, json=payload, timeout=15)

        # 5xx = transient (gateway timeout, service unavailable) — retry
        # 4xx = permanent (invalid order, expired card) — don't retry
        if resp.status_code < 500 or not RETRY_TRANSIENT_ERRORS:
            break

        if attempt < max_attempts - 1:
            wait = (attempt + 1) * 1.5  # 1.5s, 3s
            time.sleep(wait)

    return {"status_code": resp.status_code, **resp.json()}


def process_refund(order_id: str, customer_id: str) -> dict:
    """Process a refund via the process-refund edge function."""
    return _call_edge_function("process-refund", {
        "order_id": order_id, "customer_id": customer_id,
    })


def initiate_return(order_id: str, customer_id: str, reason: str) -> dict:
    """Initiate a return via the initiate-return edge function."""
    return _call_edge_function("initiate-return", {
        "order_id": order_id, "customer_id": customer_id, "reason": reason,
    })


def check_shipping_status(order_id: str) -> dict:
    """Check live shipping status via the check-shipping edge function."""
    return _call_edge_function("check-shipping", {"order_id": order_id})


def escalate_to_human(customer_id: str = None, order_id: str = None,
                       subject: str = "", description: str = "",
                       priority: str = "normal") -> dict:
    """Create a support ticket via the escalate-ticket edge function."""
    return _call_edge_function("escalate-ticket", {
        "customer_id": customer_id,
        "order_id": order_id,
        "subject": subject,
        "description": description,
        "priority": priority,
    })


# ── Tool registry (for the chatbot's tool dispatch) ─────────────────────────

TOOL_FUNCTIONS = {
    "lookup_order": lookup_order,
    "lookup_customer_by_email": lookup_customer_by_email,
    "lookup_customer_orders": lookup_customer_orders,
    "lookup_product": lookup_product,
    "check_return_eligibility": check_return_eligibility,
    "process_refund": process_refund,
    "initiate_return": initiate_return,
    "check_shipping_status": check_shipping_status,
    "escalate_to_human": escalate_to_human,
}
