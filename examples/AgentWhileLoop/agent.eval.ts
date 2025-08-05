import { Eval, EvalCase } from "braintrust";
import { WhileLoopAgent } from "./agent.js";
import { getAllTools } from "./tools.js";

type TestCase = EvalCase<
  string,
  {
    toolsUsed?: string[];
    emailsSent?: string[];
    subscriptionsUpdated?: string[];
    requiredPhrases?: string[];
  },
  {
    category: string;
    difficulty: "easy" | "medium" | "hard";
  }
>;

const testCases: TestCase[] = [
  {
    input: "Find all premium users and notify them about a new feature",
    expected: {
      toolsUsed: ["search_users", "notify_customer"],
      emailsSent: ["john@co.com"],
    },
    metadata: {
      category: "multi-step",
      difficulty: "medium",
    },
  },
  {
    input: "Check if jane@co.com is an active subscriber",
    expected: {
      toolsUsed: ["get_user_details"],
      requiredPhrases: ["Jane Doe", "Basic subscriber", "active"],
    },
    metadata: {
      category: "single-lookup",
      difficulty: "easy",
    },
  },
  {
    input: "Find expired subscriptions and send them renewal reminders",
    expected: {
      toolsUsed: ["search_users", "notify_customer"],
      emailsSent: ["bob@co.com"],
    },
    metadata: {
      category: "multi-step",
      difficulty: "medium",
    },
  },
  {
    input: "Cancel the subscription for alice@co.com",
    expected: {
      toolsUsed: ["update_subscription"],
      subscriptionsUpdated: ["alice@co.com"],
    },
    metadata: {
      category: "single-action",
      difficulty: "easy",
    },
  },
];

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

// Custom scorer to check if the right tools were used
const toolUsageScorer = {
  name: "tool_usage",
  scorer: ({ output, expected, trace }) => {
    if (!expected.toolsUsed) return { score: 1 };

    // Extract tool calls from trace
    const toolCalls = trace?.span_attributes?.tool_calls || [];
    const usedTools = toolCalls.map((call: any) => call.name);

    const expectedTools = expected.toolsUsed;
    const correctToolsUsed = expectedTools.every((tool) =>
      usedTools.includes(tool),
    );

    return {
      score: correctToolsUsed ? 1 : 0,
      metadata: {
        expected_tools: expectedTools,
        used_tools: usedTools,
        correct: correctToolsUsed,
      },
    };
  },
};

// Custom scorer to check if required content appears in the response
const contentAccuracyScorer = {
  name: "content_accuracy",
  scorer: ({ output, expected }) => {
    if (!expected.requiredPhrases) return { score: 1 };

    const phrases = expected.requiredPhrases;
    const foundPhrases = phrases.filter((phrase) =>
      output.toLowerCase().includes(phrase.toLowerCase()),
    );

    const score = foundPhrases.length / phrases.length;

    return {
      score,
      metadata: {
        required_phrases: phrases,
        found_phrases: foundPhrases,
        missing_phrases: phrases.filter((p) => !foundPhrases.includes(p)),
      },
    };
  },
};

Eval("CustomerServiceAgent", {
  data: testCases,
  task: async (input) => {
    return await agent.run(input);
  },
  scores: ["Factuality", "Helpfulness", toolUsageScorer, contentAccuracyScorer],
  experimentName: "Agent Eval",
});
