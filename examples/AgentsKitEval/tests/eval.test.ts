import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { supportAgent } from "../agent.js";
import { supportCases } from "../cases.js";
import { escalationScore, requiredTermsScore } from "../scorers.js";

describe("AgentsKit support agent evaluation", () => {
  for (const testCase of supportCases) {
    it(`passes the ${testCase.metadata.category} baseline`, async () => {
      const output = await supportAgent(testCase.input);

      assert.equal(requiredTermsScore(output, testCase.expected), 1);
      assert.equal(escalationScore(output, testCase.expected), 1);
    });
  }
});
