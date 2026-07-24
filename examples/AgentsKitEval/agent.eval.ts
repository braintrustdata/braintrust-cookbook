import { Eval } from "braintrust";
import type { EvalScorer } from "braintrust";
import type { AgentOutput } from "./agent.js";
import { supportAgent } from "./agent.js";
import type { SupportCase } from "./cases.js";
import { supportCases } from "./cases.js";
import { escalationScore, requiredTermsScore } from "./scorers.js";

const required_terms: EvalScorer<
  string,
  AgentOutput,
  SupportCase["expected"],
  SupportCase["metadata"]
> = ({ output, expected }) => requiredTermsScore(output, expected);

const safe_escalation: EvalScorer<
  string,
  AgentOutput,
  SupportCase["expected"],
  SupportCase["metadata"]
> = ({ output, expected }) => escalationScore(output, expected);

Eval("AgentsKitSupportAgent", {
  data: supportCases,
  task: supportAgent,
  scores: [required_terms, safe_escalation],
  experimentName: "AgentsKit deterministic baseline",
});
