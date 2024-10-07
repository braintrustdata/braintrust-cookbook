import braintrust from "braintrust";
import { OpenAI } from "openai";
import { Pinecone } from "@pinecone-database/pinecone";

import { PROJECT_NAME, INDEX_NAME } from "./constants";
import { z } from "zod";

const project = braintrust.projects.create({
  name: PROJECT_NAME,
});

if (!process.env.BRAINTRUST_API_KEY) {
  throw new Error("BRAINTRUST_API_KEY is not set");
}
if (!process.env.PINECONE_API_KEY) {
  throw new Error("PINECONE_API_KEY is not set");
}

const openai = new OpenAI(); // These env vars are automatically set by Braintrust
const pinecone = new Pinecone({ apiKey: process.env.PINECONE_API_KEY });
const pc = pinecone.Index(INDEX_NAME);

export const retrieval = project.tools.create({
  name: "Retrieve",
  description: "A tool for retrieving snippets from the Braintrust docs",
  parameters: z.object({
    query: z.string().describe("The query to search for"),
    top_k: z
      .number()
      .min(3)
      .max(10)
      .describe("The number of results to return"),
  }),
  handler: async ({ query, top_k }) => {
    const embedding = await openai.embeddings
      .create({
        input: query,
        model: "text-embedding-3-small",
      })
      .then((res) => res.data[0].embedding);

    const queryResponse = await pc.query({
      vector: embedding,
      topK: top_k,
      includeMetadata: true,
    });

    return queryResponse.matches.map((match) => ({
      title: match.metadata?.title,
      content: match.metadata?.content,
    }));
  },
  ifExists: "replace",
});
