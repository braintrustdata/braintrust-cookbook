import { initDataset } from "braintrust";
import { PROJECT_NAME } from "./constants";

const questions = [
  {
    question: "How do I use the openai client with Braintrust?",
    assertions: [
      "Mentions the wrapOpenAI wrapper in Typescript",
      "Mentions the wrap_openai function in Python",
    ],
  },
  {
    question:
      "Show me a full example in Python of how to create an eval for a Text-2-SQL use case",
    assertions: [
      "Uses the SQL scorer",
      "Runs the SQL query, in addition to grading the syntax",
    ],
  },
  {
    question: "How do I setup human review?",
    assertions: [
      "Mentions the configuration page",
      "Mentions that you can set it through the API and shows a code snippet",
    ],
  },
  {
    question: "How do I use a dataset in an Eval?",
    assertions: [
      "Uses the `initDataset` syntax in Typescript",
      "Uses the `init_dataset` syntax in Python",
    ],
  },
  {
    question: "Can I use Gemini models in the playground?",
    assertions: ["Says yes"],
  },
];

async function main() {
  const dataset = initDataset(PROJECT_NAME, {
    dataset: "Questions",
  });

  for (const question of questions) {
    dataset.insert({
      input: { question: question.question },
      expected: { assertions: question.assertions },
    });
  }

  await dataset.flush();
}

main().catch(console.error);
