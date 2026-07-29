import "./env.js";

import { Eval } from "braintrust";

import { loadBehaviorSpec, type BehaviorSection } from "./behavior.js";
import { CodingAgent, type AgentResult } from "./agent.js";
import { judgeBehavior } from "./judge.js";
import { scenarios, type Scenario } from "./data.js";

const behavior = loadBehaviorSpec();
const agent = new CodingAgent();

interface EvalInput {
  scenario: Scenario;
}

interface ScorerArgs {
  input: EvalInput;
  output: AgentResult;
}

interface BehaviorScore {
  name: string;
  score: number | null;
  metadata: { behavior: string; verdict: string; rationale: string };
}

// One scorer per behavior in the spec. Each scorer judges the trajectory against
// exactly one behavior and maps the verdict to a score:
//   true -> 1, false -> 0, na -> null (excluded from the average).
function makeBehaviorScorer(section: BehaviorSection) {
  const scorer = async ({ input, output }: ScorerArgs): Promise<BehaviorScore> => {
    const { verdict, rationale } = await judgeBehavior(
      section,
      input.scenario.task,
      output.transcript,
    );
    return {
      name: section.slug,
      score: verdict === "true" ? 1 : verdict === "false" ? 0 : null,
      metadata: { behavior: section.title, verdict, rationale },
    };
  };
  // Give the scorer a stable identity in the Braintrust UI.
  Object.defineProperty(scorer, "name", { value: section.slug });
  return scorer;
}

Eval("Agent Behavior — verify-before-done", {
  data: [
    { input: { scenario: scenarios.bugFix }, metadata: { scenario: scenarios.bugFix.id } },
    { input: { scenario: scenarios.explainOnly }, metadata: { scenario: scenarios.explainOnly.id } },
    { input: { scenario: scenarios.runnerDown }, metadata: { scenario: scenarios.runnerDown.id } },
  ],
  task: async (input: EvalInput) => agent.run(input.scenario),
  scores: behavior.sections.map(makeBehaviorScorer),
  metadata: {
    behavior: behavior.name,
    behaviorLocation: behavior.location,
    agentModel: process.env.MODEL ?? "gpt-4o-mini",
    judgeModel: process.env.JUDGE_MODEL ?? process.env.MODEL ?? "gpt-4o-mini",
  },
});
