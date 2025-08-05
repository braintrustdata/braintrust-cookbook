import { WhileLoopAgent } from "./agent.js";
import { getAllTools } from "./tools.js";
import { initLogger } from "braintrust";

// Initialize Braintrust logging
const logger = initLogger("CustomerServiceAgent");

const agent = new WhileLoopAgent({
  model: "gpt-4o-mini",
  systemPrompt: `You are a helpful customer service agent. You can:

1. Search for users by name, email, or subscription details
2. Get detailed information about specific users
3. Send email notifications to customers
4. Update subscription plans and statuses

Always be polite and helpful. When you need more information, ask clarifying questions.
When you complete an action, summarize what you did for the customer.`,
  tools: getAllTools(),
  maxIterations: 10,
});

// Example usage
async function main() {
  const queries = [
    "Find all premium users with expired subscriptions",
    "Get details for john@co.com and send them a renewal reminder",
    "Cancel the subscription for jane@co.com",
    "Search for users with basic plans",
  ];

  console.log("🤖 Customer Service Agent Demo");
  console.log("================================\n");

  for (const query of queries) {
    console.log(`Query: ${query}`);
    console.log("Response:", await agent.run(query));
    console.log("---\n");
  }
}

main().catch(console.error);
