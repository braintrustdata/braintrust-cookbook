import { runEval } from "@agentskit/eval";
import { supportAgent } from "./agent.js";
import { supportCases } from "./cases.js";
import { escalationScore, requiredTermsScore } from "./scorers.js";

const result = await runEval({
  agent: async (input) => {
    const output = await supportAgent(input);
    return JSON.stringify(output);
  },
  suite: {
    name: "agentskit-support-agent",
    cases: supportCases.map((testCase) => ({
      input: testCase.input,
      expected: (serializedOutput: string) => {
        const output = JSON.parse(serializedOutput) as Awaited<
          ReturnType<typeof supportAgent>
        >;
        return (
          requiredTermsScore(output, testCase.expected) === 1 &&
          escalationScore(output, testCase.expected) === 1
        );
      },
    })),
  },
});

console.log({
  accuracy: result.accuracy,
  passed: result.passed,
  totalCases: result.totalCases,
});
