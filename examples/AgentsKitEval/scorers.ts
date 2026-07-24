import type { AgentOutput } from "./agent.js";
import type { SupportCase } from "./cases.js";

export function requiredTermsScore(
  output: AgentOutput,
  expected: SupportCase["expected"],
): number {
  const answer = output.answer.toLowerCase();
  const matches = expected.requiredTerms.filter((term) =>
    answer.includes(term.toLowerCase()),
  );
  return matches.length / expected.requiredTerms.length;
}

export function escalationScore(
  output: AgentOutput,
  expected: SupportCase["expected"],
): number {
  return output.escalated === expected.escalationExpected ? 1 : 0;
}
