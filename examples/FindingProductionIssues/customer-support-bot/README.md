# Topics Customer Support Demo

Demo project for the **"Find the AI failures that testing misses"** workshop. Uses a customer support chatbot backed by a mock e-commerce database, with all conversations traced to Braintrust for Topics analysis.

## Files

- `mock_db.py` — Static mock database: 15 products, 10 customers, 15 orders (including problem orders), return policies, and lookup functions exposed as tool calls.
- `chat_app.py` — Interactive chatbot with OpenAI tool calling. The agent looks up real order data instead of fabricating it.
- `generate_logs.py` — Generates ~80 conversations (curated + templated) across 5 categories and logs them to the `Customer Support Chatbot` Braintrust project. Uses `gpt-4o-mini` to keep costs low.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=your-key
export BRAINTRUST_API_KEY=your-key
```

## Usage

**Interactive chat:**
```bash
python chat_app.py
```

**Generate logs for Topics:**
```bash
python generate_logs.py
```

After generating logs, go to the [Topics page](https://www.braintrust.dev/app/Jess%20Wang/p/Customer%20Support%20Chatbot/topics) to see clusters form.

## Workshop flow

1. Run `generate_logs.py` to populate the project with grounded conversations
2. Enable Topics (Task, Sentiment, Issues) if not already enabled
3. Explore topic clusters — notice what the built-in facets catch vs. miss
4. Create a custom "Resolution Gap" facet to surface the bot's blind spot
5. Filter by classification → build dataset → run eval → validate fix
