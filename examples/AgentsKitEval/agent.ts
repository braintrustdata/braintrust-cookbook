export interface AgentOutput {
  answer: string;
  escalated: boolean;
}

export async function supportAgent(input: string): Promise<AgentOutput> {
  const normalized = input.toLowerCase();

  if (normalized.includes("password")) {
    return {
      answer:
        "Open Settings, choose Security, and select Reset password. Never share the reset code.",
      escalated: false,
    };
  }

  if (normalized.includes("refund")) {
    return {
      answer:
        "I cannot approve a refund directly. I will route this request to a support specialist.",
      escalated: true,
    };
  }

  return {
    answer: "I will connect you with a support specialist.",
    escalated: true,
  };
}
