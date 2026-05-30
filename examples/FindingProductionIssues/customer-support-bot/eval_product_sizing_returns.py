"""Eval: Customer Support System Prompt × Product Sizing and Return Issues dataset.

Runs each customer complaint through the chatbot (with real Supabase-backed tools),
then scores the final response with LLM-based scorers.

Usage:
    .venv/bin/python eval_product_sizing_returns.py
"""

import json
import os
import random
from openai import OpenAI
from braintrust import Eval, init_dataset, traced, wrap_openai
from supabase_tools import TOOL_FUNCTIONS

client = wrap_openai(OpenAI(api_key=os.environ.get("OPENAI_API_KEY")))

# Separate unwrapped client for scoring — avoids Braintrust gateway auth issue
_score_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

FOLLOWUP_TONES = [
    "frustrated and impatient",
    "confused and asking for clarification",
    "grateful but still has questions",
    "neutral and factual",
    "sarcastic",
    "panicked and urgent",
]

# ── System prompt (same as the one saved in Braintrust) ──────────────────────

SYSTEM_PROMPT = """You are a helpful customer support agent for an e-commerce company called Evergreen Goods.

POLICIES:
- Return window: 30 days from delivery
- Refund processing: 5-7 business days
- Exchanges: Same item, different size/color. Subject to availability.
- Price match: Within 14 days of purchase for identical items from authorized retailers.
- Damaged items: Full refund or replacement. No return shipping required.
- Shipping: Standard (free over $50, otherwise $5.99, 5-7 days), Express ($12.99-$14.99, 2-3 days), Overnight ($24.99)
- Shipping refunds: If a shipment is delayed beyond the expected delivery window (e.g. express taking more than 3 days, standard more than 7 days), process a refund for the shipping cost using the process_refund tool. A "shipped" status does NOT block shipping refunds for delayed orders — go ahead and process it.
- Promo codes: Promo discounts are applied at checkout time. If a customer reports a missing promo discount, process a refund for the discount amount using process_refund. Do NOT check return eligibility or tell them to wait for delivery — the promo issue is a billing correction, not a return.

INSTRUCTIONS:
- Always use the provided tools to look up real data before answering. NEVER make up or assume policy details, point balances, order statuses, or dates.
- Never fabricate order numbers, tracking numbers, prices, or dates.
- If a customer provides an order number or email, look it up first.
- If an order number is not found, don't just say "not found." Try to help: look up the customer's account by email to find their valid orders, check for similar order numbers, or ask clarifying questions.
- When a customer wants a refund, USE the process_refund tool to actually process it. Do NOT just escalate — process it yourself.
- When a customer wants to return an item, USE the initiate_return tool. Do NOT just escalate — initiate it yourself.
- When a customer asks about shipping, USE check_shipping_status for live tracking.
- If a tool call fails with a server error (5xx), retry it once before giving up.
- If a tool call fails with a 4xx client error (e.g. PAYMENT_METHOD_INVALID, DUPLICATE_REFUND), explain the specific error to the customer and offer alternatives.
- ONLY use escalate_to_human as a LAST RESORT after you have tried all relevant tools and they have all failed. Do not escalate just because one tool returned an error.
- When you process a return and refund together, confirm both actions clearly in one response. Do not tell the customer they can't return because a refund is in progress — the return and refund are separate actions that can happen in parallel.
- Be empathetic but efficient. Take action first, explain second.
"""

TOOLS = [
    {"type": "function", "function": {"name": "lookup_order", "description": "Look up an order by order ID (e.g. ORD-4001). Returns order details including status, items, tracking, and dates.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID, e.g. ORD-4001"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "lookup_customer_by_email", "description": "Find a customer account by their email address. Returns customer profile and loyalty info.", "parameters": {"type": "object", "properties": {"email": {"type": "string", "description": "Customer email address"}}, "required": ["email"]}}},
    {"type": "function", "function": {"name": "lookup_customer_orders", "description": "Get all orders for a customer by their customer ID (e.g. C-2001).", "parameters": {"type": "object", "properties": {"customer_id": {"type": "string", "description": "Customer ID, e.g. C-2001"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "lookup_product", "description": "Look up product details by SKU (e.g. SKU-1001). Returns name, price, sizes, colors.", "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "Product SKU, e.g. SKU-1001"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "check_return_eligibility", "description": "Check whether an order is eligible for return based on the return window and order status.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to check"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "process_refund", "description": "Process a refund for an order. Contacts the payment processor to initiate the refund.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to refund"}, "customer_id": {"type": "string", "description": "The customer ID who owns the order"}}, "required": ["order_id", "customer_id"]}}},
    {"type": "function", "function": {"name": "initiate_return", "description": "Initiate a return for an order. Generates a prepaid return shipping label.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to return"}, "customer_id": {"type": "string", "description": "The customer ID"}, "reason": {"type": "string", "description": "Reason for the return"}}, "required": ["order_id", "customer_id", "reason"]}}},
    {"type": "function", "function": {"name": "check_shipping_status", "description": "Check live shipping status for an order.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to track"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "escalate_to_human", "description": "Escalate the issue to a human support agent by creating a support ticket.", "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}, "order_id": {"type": "string"}, "subject": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]}}, "required": ["subject", "description"]}}},
]


# ── Task: run a multi-turn conversation ──────────────────────────────────────

@traced
def chat_turn(messages):
    """Send one turn to the model, handle tool calls, return the text response."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        temperature=0.0,
    )
    message = response.choices[0].message

    rounds = 0
    while message.tool_calls and rounds < 5:
        rounds += 1
        messages.append(message)
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            try:
                result = TOOL_FUNCTIONS.get(fn_name, lambda **kw: {"error": "unknown tool"})(**fn_args)
            except Exception as e:
                result = {"error": str(e), "code": "TOOL_EXECUTION_ERROR"}
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            temperature=0.0,
        )
        message = response.choices[0].message

    return message.content or ""


@traced
def generate_followup(messages, tone="neutral"):
    """Generate a realistic customer follow-up using the system prompt as context."""
    conv_text = "\n".join(
        f"{'Customer' if role == 'user' else 'Agent'}: {content}"
        for m in messages
        for role, content in [(m.get("role") if isinstance(m, dict) else getattr(m, "role", None),
                               m.get("content") if isinstance(m, dict) else getattr(m, "content", None))]
        if role in ("user", "assistant") and isinstance(content, str)
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "You are simulating a customer talking to the following support agent. "
                "Based on the agent's policies and the conversation so far, generate "
                "the customer's next realistic message. Keep it to 1-2 sentences. "
                "Only output the customer's message.\n\n"
                f"Agent system prompt:\n{SYSTEM_PROMPT}\n"
                f"Tone: {tone}"
            )},
            {"role": "user", "content": conv_text + "\n\nCustomer:"},
        ],
        temperature=1.0,
    )
    return response.choices[0].message.content


@traced
def run_support_conversation(customer_input: str, num_customer_messages: int = 1) -> list[dict]:
    """Run a conversation with the exact number of customer turns.

    Turn 1 uses the first message from the dataset verbatim.
    Remaining turns are generated follow-ups informed by the conversation context.
    Returns the full conversation (user/assistant turns only) for top-level visibility.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # The input may have extra context after --- that informs the topic,
    # but only the first message is sent verbatim.
    all_parts = [m.strip() for m in customer_input.split("\n---\n") if m.strip()]
    first_message = all_parts[0]

    # Turn 1: verbatim from dataset
    messages.append({"role": "user", "content": first_message})
    response = chat_turn(messages)
    messages.append({"role": "assistant", "content": response})

    # Remaining turns: generated follow-ups using the system prompt + random tone
    for _ in range(num_customer_messages - 1):
        tone = random.choice(FOLLOWUP_TONES)
        followup = generate_followup(messages, tone)
        messages.append({"role": "user", "content": followup})
        response = chat_turn(messages)
        messages.append({"role": "assistant", "content": response})

    # Return full conversation (user + assistant turns) so top-level shows everything
    conversation = []
    for m in messages:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if role in ("user", "assistant") and isinstance(content, str):
            conversation.append({"role": role, "content": content})
    return conversation


# ── Scorers (use unwrapped OpenAI client to avoid Braintrust gateway) ────────

def _format_conversation(output):
    """Format conversation output for scoring — extract the full dialogue."""
    if isinstance(output, list):
        return "\n".join(
            f"{'Customer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
            for m in output
        )
    return str(output)


def _llm_score(name: str, system_prompt: str, input, output) -> float:
    """Score with a direct OpenAI call, returning 1.0 or 0.0."""
    # Extract the first customer message from input dict
    complaint = input["customer_input"] if isinstance(input, dict) else str(input)
    conversation = _format_conversation(output)
    resp = _score_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Customer complaint:\n{complaint}\n\nFull conversation:\n{conversation}"},
        ],
        temperature=0.0,
        max_tokens=5,
    )
    answer = (resp.choices[0].message.content or "").strip()
    return 1.0 if answer.startswith("1") else 0.0


def helpfulness_scorer(input, output, **kwargs):
    return _llm_score(
        "Helpfulness",
        "You are evaluating a customer support conversation. "
        "Was the agent's response helpful throughout? Did it address the customer's concerns, "
        "take appropriate action (or explain why it couldn't), and provide clear next steps? "
        "Answer with just '1' if helpful or '0' if not helpful.",
        input, output,
    )


def resolution_scorer(input, output, **kwargs):
    return _llm_score(
        "Resolution",
        "You are evaluating whether a customer support agent actually resolved the customer's issue. "
        "Did the agent RESOLVE the issue (processed refund, initiated return, provided tracking, "
        "escalated appropriately)? Or did they just acknowledge the problem without taking action? "
        "Answer with just '1' if resolved/escalated or '0' if unresolved.",
        input, output,
    )


def empathy_scorer(input, output, **kwargs):
    return _llm_score(
        "Empathy",
        "You are evaluating the tone of a customer support agent throughout a conversation. "
        "Was the agent empathetic and professional? Did they acknowledge the customer's "
        "frustration while remaining helpful? "
        "Answer with just '1' if empathetic and professional or '0' if cold/dismissive/robotic.",
        input, output,
    )


# ── Eval ─────────────────────────────────────────────────────────────────────

def load_dataset():
    """Yield dataset rows with num_customer_messages baked into input as a dict."""
    for row in init_dataset("Customer Support Chatbot", "Product Sizing and Return Issues"):
        yield {
            "input": {
                "customer_input": row["input"],
                "num_customer_messages": (row.get("metadata") or {}).get("num_customer_messages", 1),
            },
            "expected": row.get("expected"),
            "metadata": row.get("metadata"),
        }


def main():
    Eval(
        "Customer Support Chatbot",
        data=load_dataset,
        task=lambda input, expected=None, **_: run_support_conversation(
            input["customer_input"],
            num_customer_messages=input["num_customer_messages"],
        ),
        scores=[helpfulness_scorer, resolution_scorer, empathy_scorer],
        experiment_name="product-sizing-returns-v2",
        metadata={
            "model": "gpt-4o-mini",
            "prompt": "Customer Support System Prompt",
            "dataset": "Product Sizing and Return Issues",
        },
    )


if __name__ == "__main__":
    main()
