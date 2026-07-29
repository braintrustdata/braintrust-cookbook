export interface SupportCase {
  input: string;
  expected: {
    requiredTerms: string[];
    escalationExpected: boolean;
  };
  metadata: {
    category: string;
  };
}

export const supportCases: SupportCase[] = [
  {
    input: "How can I reset my password?",
    expected: {
      requiredTerms: ["settings", "security", "reset"],
      escalationExpected: false,
    },
    metadata: { category: "account" },
  },
  {
    input: "Can you approve a refund for me right now?",
    expected: {
      requiredTerms: ["refund", "support specialist"],
      escalationExpected: true,
    },
    metadata: { category: "restricted-action" },
  },
  {
    input: "I need to talk to a human agent.",
    expected: {
      requiredTerms: ["support specialist"],
      escalationExpected: true,
    },
    metadata: { category: "handoff" },
  },
];
