import "./env.js";

import { initLogger } from "braintrust";

import { CodingAgent } from "./agent.js";
import { scenarios } from "./data.js";

// Run the agent on each scenario and print the trajectory. Every run is logged
// to Braintrust so you can inspect the trace, then judge it against the spec
// with `npm run eval`.
initLogger({ projectName: "Agent Behavior — verify-before-done" });

async function main() {
  const agent = new CodingAgent();

  for (const key of Object.keys(scenarios)) {
    const scenario = scenarios[key];
    console.log(`\n=== ${scenario.id} ===`);
    const result = await agent.run(scenario);
    console.log(result.transcript);
    console.log(`\n--- final report ---\n${result.answer}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
