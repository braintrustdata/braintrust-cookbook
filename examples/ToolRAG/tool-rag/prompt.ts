import braintrust from "braintrust";
import { PROJECT_NAME } from "./constants";
import { retrieval } from "./retrieval";

const project = braintrust.projects.create({
  name: PROJECT_NAME,
});

export const prompt = project.prompts.create({
  name: "Doc Search",
  messages: [
    {
      role: "system",
      content:
        "You are a helpful assistant that can " +
        "answer questions about the Braintrust documentation.",
    },
    {
      role: "user",
      content: "{{{question}}}",
    },
  ],
  model: "gpt-4o-mini",
  tools: [retrieval],
  ifExists: "replace",
});
