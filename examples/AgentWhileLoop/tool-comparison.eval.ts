import { Eval, EvalCase } from "braintrust";
import { WhileLoopAgent } from "./agent.js";
import { getAllTools } from "./tools.js";
import { getGenericTools } from "./generic-tools.js";

type TestCase = EvalCase<
  string,
  {
    successCriteria: string[];
    requiredActions?: string[];
  },
  {
    category: string;
    difficulty: "easy" | "medium" | "hard";
  }
>;

const testCases: TestCase[] = [
  {
    input: "Find all premium users and notify them about a new feature launch",
    expected: {
      successCriteria: [
        "Found premium users",
        "Sent notifications to premium users",
        "john@co.com",
        "bob@co.com",
      ],
      requiredActions: ["search", "notify"],
    },
    metadata: {
      category: "multi-step",
      difficulty: "medium",
    },
  },
  {
    input:
      "Check if jane@co.com is an active subscriber and what plan they have",
    expected: {
      successCriteria: ["Jane Doe", "jane@co.com", "active", "basic"],
      requiredActions: ["lookup"],
    },
    metadata: {
      category: "single-lookup",
      difficulty: "easy",
    },
  },
  {
    input:
      "Find users with expired subscriptions and send them renewal reminders with a special offer",
    expected: {
      successCriteria: ["expired", "Bob Wilson", "renewal", "reminder"],
      requiredActions: ["search", "notify"],
    },
    metadata: {
      category: "multi-step",
      difficulty: "medium",
    },
  },
  {
    input: "Upgrade jane@co.com to premium plan and send confirmation",
    expected: {
      successCriteria: ["upgrade", "premium", "jane@co.com", "confirmation"],
      requiredActions: ["update", "notify"],
    },
    metadata: {
      category: "multi-step",
      difficulty: "medium",
    },
  },
  {
    input: "List all active users sorted by subscription type",
    expected: {
      successCriteria: ["John Smith", "Jane Doe", "active", "premium", "basic"],
      requiredActions: ["search"],
    },
    metadata: {
      category: "single-lookup",
      difficulty: "easy",
    },
  },
];

// Scorer for checking if the agent accomplished the task
const taskSuccessScorer = ({
  output,
  expected,
}: {
  output: string;
  expected: TestCase["expected"];
}) => {
  if (!expected?.successCriteria) return null;

  const foundCriteria = expected.successCriteria.filter((criteria) =>
    output.toLowerCase().includes(criteria.toLowerCase()),
  );

  const score = foundCriteria.length / expected.successCriteria.length;

  return {
    name: "task_success",
    score,
    metadata: {
      expected_criteria: expected.successCriteria,
      found_criteria: foundCriteria,
      missing_criteria: expected.successCriteria.filter(
        (c) => !foundCriteria.includes(c),
      ),
    },
  };
};

// Scorer for response clarity
const clarityScorer = ({ output }: { output: string }) => {
  // Check for clear, structured responses
  const hasStructure =
    output.includes("\n") || output.includes("•") || output.includes("-");
  const hasConfirmation =
    output.includes("✓") ||
    output.includes("successfully") ||
    output.includes("completed");
  const isVerbose = output.length > 1000;
  const hasJson = output.includes("{") && output.includes("}");
  const hasRawData =
    output.includes("query_id") ||
    output.includes("request_id") ||
    output.includes("transaction_id");
  const hasError = output.includes("Error:") || output.includes("error");

  let score = 0.5;
  if (
    hasStructure &&
    hasConfirmation &&
    !isVerbose &&
    !hasJson &&
    !hasRawData &&
    !hasError
  ) {
    score = 1.0;
  } else if ((hasStructure || hasConfirmation) && !hasError) {
    score = 0.7;
  } else if (hasJson || isVerbose || hasRawData || hasError) {
    score = 0.3;
  }

  return {
    name: "clarity",
    score,
    metadata: {
      hasStructure,
      hasConfirmation,
      isVerbose,
      hasJson,
      hasRawData,
      hasError,
      responseLength: output.length,
    },
  };
};

// Same system prompt for both evaluations
const systemPrompt = `You are a customer service assistant. Help users manage customer accounts and subscriptions.

When asked to find and notify users:
- First find the relevant users
- Then send notifications to each user
- Be specific about what actions you're taking
- Provide clear confirmation of completed tasks`;

// Evaluation with specific tools
Eval("agent-while-loop", {
  experimentName: "specific-tools",
  data: testCases,
  task: async (input) => {
    const agent = new WhileLoopAgent({
      tools: getAllTools(),
      systemPrompt,
      maxIterations: 10,
    });

    const output = await agent.run(input);
    return output;
  },
  scores: [taskSuccessScorer, clarityScorer],
  metadata: {
    description: "Evaluation using purpose-built, specific tools",
    toolType: "specific",
  },
});

// Evaluation with generic tools
Eval("agent-while-loop", {
  experimentName: "generic-tools",
  data: testCases,
  task: async (input) => {
    const agent = new WhileLoopAgent({
      tools: getGenericTools(),
      systemPrompt,
      maxIterations: 10,
    });

    const output = await agent.run(input);
    return output;
  },
  scores: [taskSuccessScorer, clarityScorer],
  metadata: {
    description: "Evaluation using generic API wrapper tools",
    toolType: "generic",
  },
});
