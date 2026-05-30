"""Generate customer support conversations backed by Supabase.

Every tool call is a real HTTP request — reads go to Supabase REST,
actions go to Edge Functions that talk to the DB and can genuinely fail
(payment timeouts, expired cards, label service down, tracking not found).

Logs are sent to the Braintrust project for Topics analysis.

Usage:
    export SUPABASE_SERVICE_ROLE_KEY=your-key
    export OPENAI_API_KEY=your-key
    export BRAINTRUST_API_KEY=your-key
    python generate_logs.py
"""

import json
import os
import random
from openai import OpenAI
from braintrust import init_logger, traced, wrap_openai
from supabase_tools import TOOL_FUNCTIONS

logger = init_logger(project="Customer Support Chatbot")
client = wrap_openai(OpenAI(api_key=os.environ.get("OPENAI_API_KEY")))

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
    {"type": "function", "function": {"name": "lookup_order", "description": "Look up an order by order ID (e.g. ORD-4001).", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "lookup_customer_by_email", "description": "Find a customer by email.", "parameters": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}}},
    {"type": "function", "function": {"name": "lookup_customer_orders", "description": "Get all orders for a customer.", "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "lookup_product", "description": "Look up a product by SKU.", "parameters": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "check_return_eligibility", "description": "Check if an order is eligible for return.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "process_refund", "description": "Process a refund for an order. Contacts payment processor. May fail.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}, "customer_id": {"type": "string"}}, "required": ["order_id", "customer_id"]}}},
    {"type": "function", "function": {"name": "initiate_return", "description": "Initiate a return and generate a shipping label. May fail.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}, "customer_id": {"type": "string"}, "reason": {"type": "string"}}, "required": ["order_id", "customer_id", "reason"]}}},
    {"type": "function", "function": {"name": "check_shipping_status", "description": "Check live shipping status from the carrier API.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "escalate_to_human", "description": "Create a support ticket to escalate to a human agent.", "parameters": {"type": "object", "properties": {"customer_id": {"type": "string"}, "order_id": {"type": "string"}, "subject": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]}}, "required": ["subject", "description"]}}},
]

# ── Scenarios ────────────────────────────────────────────────────────────────

SCENARIOS = [
    # (first_message, followups, category)
    # -- Shipping (will trigger check_shipping_status) --
    ("Where is my order ORD-4002? It's been 5 days and still no delivery.", ["Can you give me a more specific ETA?"], "shipping"),
    ("I paid for express shipping on ORD-4006 and it's been 8 days. This is ridiculous.", ["I want a refund on the shipping cost at minimum."], "shipping"),
    ("Can you check the tracking for ORD-4001? The link in my email isn't working.", [], "shipping"),
    ("My order ORD-4003 was split into two shipments. When does the second arrive?", ["The jacket arrived but not the beanie."], "shipping"),
    ("I just placed ORD-4005 yesterday. Can I upgrade to express shipping?", [], "shipping"),
    ("My order ORD-4002 hasn't arrived yet. Can you check the status?", ["I need it by this weekend."], "shipping"),
    ("The tracking for ORD-4006 hasn't updated in 3 days. What's going on?", [], "shipping"),
    ("My order ORD-4001 was marked as delivered but I never received it.", ["I have a Ring camera and no one came to my door."], "shipping"),
    ("I need proof of delivery for ORD-4003 for an insurance claim.", [], "shipping"),
    ("Can someone else sign for ORD-4002 if I'm not home?", [], "shipping"),

    # -- Returns (will trigger initiate_return + check_return_eligibility) --
    ("I need to return ORD-4007. I ordered a size S but I actually need a M. My email is lisa.n@example.com.", ["Can I do an exchange instead of a refund?"], "returns"),
    ("I want to return ORD-4008. The jacket doesn't fit right. Email: carlos.m@example.com.", ["I know it might be past the window. I was traveling.", "Can I get store credit at least?"], "returns"),
    ("The Bluetooth speaker from ORD-4010 doesn't turn on. Dead on arrival. My email is jwilson@example.com.", ["I want a refund, not a replacement. This is unacceptable."], "returns"),
    ("I got my order ORD-4009 but the water bottle is missing. Email: sarah.chen@example.com.", ["I checked the packing slip and it lists both items."], "returns"),
    ("I want to return ORD-4001. The product doesn't match the photos. Email: sarah.chen@example.com.", [], "returns"),
    ("How do I start a return for ORD-4003? Email: priya.p@example.com.", ["Do I need the original packaging?"], "returns"),
    ("The stitching on my item from ORD-4013 is already coming undone. Email: alex.park@example.com.", ["This is supposed to be a premium product."], "returns"),
    ("I received the wrong color in ORD-4007. Ordered white, got navy. Email: lisa.n@example.com.", [], "returns"),
    ("I bought ORD-4004 as a gift and they don't like it. Can I return it? Email: jwilson@example.com.", [], "returns"),
    ("The item from ORD-4011 smells like chemicals. Email: rachel.f@example.com.", ["I don't feel safe using it. Full refund please."], "returns"),

    # -- Refunds (will trigger process_refund) --
    ("I was charged twice — ORD-4011 and ORD-4012 are identical. I only placed one order. My email is rachel.f@example.com.", ["Please refund the duplicate."], "billing"),
    ("I cancelled ORD-4015 right after placing it. Has my refund been processed? Email: emma.t@example.com.", [], "billing"),
    ("I was charged $5.99 shipping on ORD-4002 but my order is over $50. Email: mike.r@example.com.", ["Your website says free shipping over $50."], "billing"),
    ("I want a full refund for ORD-4010. Defective product. Email: jwilson@example.com.", ["Process the refund now, not later."], "billing"),
    ("I need a refund for ORD-4001. Email: sarah.chen@example.com.", [], "billing"),
    ("My refund for ORD-4014 was supposed to arrive last week. Email: priya.p@example.com.", ["When exactly will it hit my card?"], "billing"),
    ("I see a pending charge for ORD-4004 but it shows as delivered. Email: jwilson@example.com.", [], "billing"),
    ("I applied a promo code on ORD-4005 but wasn't given the discount. Email: emma.t@example.com.", ["The code was SUMMER20."], "billing"),

    # -- Account (will trigger lookup_customer_by_email) --
    ("My email is sarah.chen@example.com. Can you check my loyalty points balance?", ["When do my Gold perks expire?"], "account"),
    ("I'm a Gold member but I didn't get my birthday discount. Email: jwilson@example.com.", ["This is really disappointing for a loyal customer."], "account"),
    ("I just signed up. Email: dkim@example.com. How do I earn Bronze tier perks?", [], "account"),
    ("Can you check my account? Email: alex.park@example.com. I think someone else is placing orders.", ["I see orders I didn't make. This is urgent."], "account"),
    ("I can't log into my account. My email is mike.r@example.com.", ["I've tried resetting my password 3 times."], "account"),
    ("My rewards points disappeared. Email: lisa.n@example.com.", ["I had over 3000 points. Where are they?"], "account"),

    # -- Account (unknown emails) --
    ("I can't log in. My email is jenny.zhao@example.com. I've been a customer for years.", ["That's impossible. I've ordered from you multiple times."], "account"),
    ("My email is tom.baker@example.com. I never got my welcome discount.", ["I signed up last week. Check again please."], "account"),
    ("I think someone hacked my account. Email dan.white@example.com.", ["This is really scary. What do I do?"], "account"),

    # -- Product questions (will trigger lookup_product) --
    ("Does the Waterproof Shell Jacket (SKU-1004) come in size XS?", [], "product"),
    ("What's the fill power on the Ultralight Down Jacket (SKU-1009)?", ["Is it waterproof or just water resistant?"], "product"),
    ("Do the Trail Runner Pro shoes (SKU-1003) run true to size?", ["What's the return policy if they don't fit?"], "product"),
    ("Is the Bluetooth Speaker (SKU-1012) waterproof?", [], "product"),
    ("Can you compare the Canvas Backpack (SKU-1010) vs the Weekender Duffel (SKU-1006)?", [], "product"),
    ("What's the battery life on the Wireless Earbuds (SKU-1005)?", [], "product"),
    ("Is the Premium Hoodie (SKU-1002) true to size? I'm between M and L.", [], "product"),
    ("What colors does the Ceramic Travel Mug (SKU-1014) come in?", [], "product"),

    # -- Orders not in system (will trigger lookup failures) --
    ("Where is my order ORD-9901? I placed it last week.", ["Can you check by my email? sarah.chen@example.com"], "shipping"),
    ("I need to return ORD-9902. The product was defective.", ["That can't be right. I have a confirmation email."], "returns"),
    ("I was charged for ORD-9903 but I cancelled it. Where's my refund?", ["I'm going to file a chargeback."], "billing"),
    ("I want a refund for ORD-9905. Dead on arrival.", ["Check again. I ordered it two weeks ago."], "returns"),
    ("My order ORD-9909 was marked delivered but nothing showed up.", ["I have cameras. No one came."], "shipping"),
    ("I was double-charged for ORD-9912. Two identical charges.", ["I only clicked submit once."], "billing"),
]

FOLLOWUP_TONES = [
    "frustrated and impatient",
    "confused and asking for clarification",
    "grateful but still has questions",
    "neutral and factual",
    "sarcastic",
    "panicked and urgent",
]

FOLLOWUP_SYSTEM_PROMPT = (
    "You are simulating a customer in a support conversation. "
    "Based on the conversation so far, generate the customer's next message. "
    "Be realistic. Keep it to 1-2 sentences. Only output the customer's message."
)


@traced
def chat_with_tools(conversation_history):
    """Chat with tool calling support — all tools hit real Supabase endpoints."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history,
        tools=TOOLS,
        temperature=1.0,
    )
    message = response.choices[0].message

    max_rounds = 5  # Safety limit to prevent infinite tool loops
    rounds = 0
    while message.tool_calls and rounds < max_rounds:
        rounds += 1
        conversation_history.append(message)
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            try:
                result = TOOL_FUNCTIONS.get(fn_name, lambda **kw: {"error": "unknown tool"})(**fn_args)
            except Exception as e:
                result = {"error": str(e), "code": "TOOL_EXECUTION_ERROR"}
            conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history,
            tools=TOOLS,
            temperature=1.0,
        )
        message = response.choices[0].message

    return message.content or ""


@traced
def generate_followup(conversation_history, tone="neutral"):
    """Generate a realistic customer follow-up message."""
    conv_text = "\n".join(
        f"{'Customer' if role == 'user' else 'Agent'}: {content}"
        for m in conversation_history
        for role, content in [(m.get("role") if isinstance(m, dict) else getattr(m, "role", None),
                               m.get("content") if isinstance(m, dict) else getattr(m, "content", None))]
        if role in ("user", "assistant") and isinstance(content, str)
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT + f"\nTone: {tone}"},
            {"role": "user", "content": conv_text + "\n\nCustomer:"},
        ],
        temperature=1.0,
    )
    return response.choices[0].message.content


def run_conversation(first_message, followups, category, num_extra_turns=0, index=0, total=0):
    """Run a single conversation and log it."""
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    with logger.start_span(name="conversation") as conversation_span:
        # Turn 1
        conversation_history.append({"role": "user", "content": first_message})
        with conversation_span.start_span(name="turn_1") as turn_span:
            response = chat_with_tools(conversation_history)
            conversation_history.append({"role": "assistant", "content": response})
            turn_span.log(input=first_message, output=response, metadata={"turn_number": 1})

        turn = 1

        # Scripted follow-ups
        for followup_msg in followups:
            turn += 1
            conversation_history.append({"role": "user", "content": followup_msg})
            with conversation_span.start_span(name=f"turn_{turn}") as turn_span:
                response = chat_with_tools(conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                turn_span.log(input=followup_msg, output=response, metadata={"turn_number": turn})

        # Extra generated turns
        for _ in range(num_extra_turns):
            turn += 1
            tone = random.choice(FOLLOWUP_TONES)
            user_msg = generate_followup(conversation_history, tone)
            conversation_history.append({"role": "user", "content": user_msg})
            with conversation_span.start_span(name=f"turn_{turn}") as turn_span:
                response = chat_with_tools(conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                turn_span.log(input=user_msg, output=response, metadata={"turn_number": turn})

        conversation_span.log(
            input=conversation_history,
            output=conversation_history[-1]["content"],
            metadata={"total_turns": turn, "category": category},
        )

    if index % 10 == 0 or index == total:
        print(f"  [{index}/{total}] {category}: {first_message[:55]}...")


def main():
    all_scenarios = list(SCENARIOS)
    total = len(all_scenarios)
    print(f"Generating {total} conversations with Supabase-backed tools...")
    print("(Reads → Supabase REST, Actions → Edge Functions)\n")

    random.shuffle(all_scenarios)

    for i, (msg, followups, category) in enumerate(all_scenarios, 1):
        extra_turns = random.choice([0, 0, 0, 1, 1, 2])
        try:
            run_conversation(msg, followups, category, extra_turns, i, total)
        except Exception as e:
            print(f"  [{i}/{total}] ERROR: {e}")

    print(f"\nDone. Logged {total} conversations to 'Customer Support Chatbot'.")
    print("Go to Topics to see clusters form — including Issues from tool failures.")


if __name__ == "__main__":
    main()
