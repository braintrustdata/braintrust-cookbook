import braintrust from "braintrust";
import { OpenAI } from "openai";
import { MongoClient } from "mongodb";
import { PROJECT_NAME } from "./constants";
import { z } from "zod";

if (!process.env.BRAINTRUST_API_KEY) {
  throw new Error("BRAINTRUST_API_KEY is not set");
}
if (!process.env.MONGO_URI) {
  throw new Error("MONGO_URI is not set");
}

const openai = new OpenAI({
  baseURL: "https://api.braintrust.dev/v1/proxy",
  apiKey: process.env.BRAINTRUST_API_KEY,
});
const client = new MongoClient(process.env.MONGO_URI);

const project = braintrust.projects.create({
  name: PROJECT_NAME,
});

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
    // Connect to MongoDB and select the database and collection
    await client.connect();
    const db = client.db("braintrust-docs"); // Replace with your database name
    const collection = db.collection("documents"); // Replace with your collection name

    // Generate the embedding for the query
    const embedding = await openai.embeddings
      .create({
        input: query,
        model: "text-embedding-3-small",
      })
      .then((res) => res.data[0].embedding);

    // Perform the vector search in MongoDB Atlas
    try {
      const queryResponse = await collection
        .aggregate([
          {
            $search: {
              index: "INDEX_NAME", // Replace with your MongoDB Atlas Search index name
              knnBeta: {
                vector: embedding,
                path: "embedding",
                k: top_k,
                numCandidates: 100, // Adjust based on performance
                similarity: "cosine" // Match the similarity measure you configured in Atlas
              },
            },
          },
          {
            $project: {
              title: 1,
              content: 1,
              score: { $meta: "searchScore" },
            },
          },
        ])
        .toArray();

      // Return the results in the format expected
      return queryResponse.map((match) => ({
        title: match.title,
        content: match.content,
      }));
    } catch (error) {
      console.error("Error executing MongoDB vector search:", error);
      throw new Error("Vector search failed due to a server error.");
    } finally {
      await client.close(); // Ensure connection is closed to prevent leaks
    }
  },
  ifExists: "replace",
});
