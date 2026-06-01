"""Interactive customer support chatbot backed by Supabase.

Read tools query the Supabase REST API. Action tools call Edge Functions
that process refunds, initiate returns, check live shipping, and escalate
to human agents. All calls are real HTTP requests traced to Braintrust.

Usage:
    export SUPABASE_SERVICE_ROLE_KEY=your-key
    export OPENAI_API_KEY=your-key
    python chat_app.py
"""

import json
import os
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

INSTRUCTIONS:
- Always use the provided tools to look up real data before answering.
- Never fabricate order numbers, tracking numbers, prices, or dates.
- If a customer provides an order number or email, look it up first.
- When a customer wants a refund, USE the process_refund tool to actually process it.
- When a customer wants to return an item, USE the initiate_return tool.
- When a customer asks about shipping, USE check_shipping_status for live tracking.
- If you cannot resolve an issue, USE escalate_to_human to create a support ticket.
- Be empathetic but efficient. Take action when you can.
"""

TOOLS = [
    # -- Read tools --
    {"type": "function", "function": {"name": "lookup_order", "description": "Look up an order by order ID (e.g. ORD-4001). Returns order details including status, items, tracking, and dates.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID, e.g. ORD-4001"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "lookup_customer_by_email", "description": "Find a customer account by their email address. Returns customer profile and loyalty info.", "parameters": {"type": "object", "properties": {"email": {"type": "string", "description": "Customer email address"}}, "required": ["email"]}}},
    {"type": "function", "function": {"name": "lookup_customer_orders", "description": "Get all orders for a customer by their customer ID (e.g. C-2001).", "parameters": {"type": "object", "properties": {"customer_id": {"type": "string", "description": "Customer ID, e.g. C-2001"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {"name": "lookup_product", "description": "Look up product details by SKU (e.g. SKU-1001). Returns name, price, sizes, colors.", "parameters": {"type": "object", "properties": {"sku": {"type": "string", "description": "Product SKU, e.g. SKU-1001"}}, "required": ["sku"]}}},
    {"type": "function", "function": {"name": "check_return_eligibility", "description": "Check whether an order is eligible for return based on the return window and order status.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to check"}}, "required": ["order_id"]}}},
    # -- Action tools --
    {"type": "function", "function": {"name": "process_refund", "description": "Process a refund for an order. Contacts the payment processor to initiate the refund. May fail if payment method is invalid or processor is down.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to refund"}, "customer_id": {"type": "string", "description": "The customer ID who owns the order"}}, "required": ["order_id", "customer_id"]}}},
    {"type": "function", "function": {"name": "initiate_return", "description": "Initiate a return for an order. Generates a prepaid return shipping label. May fail if label service is down or address can't be verified.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to return"}, "customer_id": {"type": "string", "description": "The customer ID"}, "reason": {"type": "string", "description": "Reason for the return (e.g. wrong_size, defective, changed_mind)"}}, "required": ["order_id", "customer_id", "reason"]}}},
    {"type": "function", "function": {"name": "check_shipping_status", "description": "Check live shipping status for an order by querying the carrier's tracking API. Returns tracking events and estimated delivery.", "parameters": {"type": "object", "properties": {"order_id": {"type": "string", "description": "The order ID to track"}}, "required": ["order_id"]}}},
    {"type": "function", "function": {"name": "escalate_to_human", "description": "Escalate the issue to a human support agent by creating a support ticket. Use when you cannot resolve the issue yourself.", "parameters": {"type": "object", "properties": {"customer_id": {"type": "string", "description": "The customer ID (if known)"}, "order_id": {"type": "string", "description": "The related order ID (if applicable)"}, "subject": {"type": "string", "description": "Brief subject line for the ticket"}, "description": {"type": "string", "description": "Detailed description of the issue and what has been tried"}, "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "description": "Ticket priority"}}, "required": ["subject", "description"]}}},
]


@traced
def chat(conversation_history):
    """Send the conversation to the model, handle tool calls, return final response."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_history,
        tools=TOOLS,
        temperature=1.0,
    )
    message = response.choices[0].message

    while message.tool_calls:
        conversation_history.append(message)
        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            try:
                result = TOOL_FUNCTIONS[fn_name](**fn_args)
            except Exception as e:
                result = {"error": str(e), "code": "TOOL_EXECUTION_ERROR"}
            conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_history,
            tools=TOOLS,
            temperature=1.0,
        )
        message = response.choices[0].message

    return message.content


def main():
    print("Evergreen Goods Customer Support (type 'quit' to exit)")
    print("-" * 55)

    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    turn_number = 0

    with logger.start_span(name="conversation") as conversation_span:
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() == "quit":
                break

            conversation_history.append({"role": "user", "content": user_input})
            turn_number += 1

            with conversation_span.start_span(name=f"turn_{turn_number}") as turn_span:
                response = chat(conversation_history)
                conversation_history.append({"role": "assistant", "content": response})
                turn_span.log(
                    input=user_input,
                    output=response,
                    metadata={"turn_number": turn_number},
                )

            print(f"\nAgent: {response}")

        conversation_span.log(
            input=conversation_history,
            output=conversation_history[-1]["content"] if len(conversation_history) > 1 else None,
            metadata={"total_turns": turn_number},
        )


if __name__ == "__main__":
    main()
