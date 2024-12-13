import { OpenAI } from "openai";
import dotenv from "dotenv";
import path from "path";

dotenv.config({ path: path.resolve(__dirname, '../.env') });

const openai = new OpenAI({
  baseURL: "https://api.braintrust.dev/v1/proxy",
  apiKey: process.env.BRAINTRUST_API_KEY,
  defaultHeaders: {
    'Authorization': `Bearer ${process.env.BRAINTRUST_API_KEY}`,
    'Content-Type': 'application/json',
  }
});

async function withRetry<T>(
  fn: () => Promise<T>, 
  retries = 3, 
  delayMs = 1000
): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (retries > 0) {
      await new Promise(resolve => setTimeout(resolve, delayMs));
      return withRetry(fn, retries - 1, delayMs * 2);
    }
    throw error;
  }
}

let pendingRequest: Promise<number[]> | null = null;

async function encodeQueryToVector(query: string): Promise<number[]> {
  if (!process.env.BRAINTRUST_API_KEY) {
    throw new Error("BRAINTRUST_API_KEY is not set");
  }

  if (pendingRequest) {
    await pendingRequest;
  }

  try {
    pendingRequest = withRetry(async () => {
      const response = await openai.embeddings.create({
        input: query.trim(),
        model: "text-embedding-3-small",
      });

      if (!response.data?.[0]?.embedding) {
        throw new Error("No embedding returned from API");
      }

      return response.data[0].embedding;
    });

    const result = await pendingRequest;
    pendingRequest = null;
    return result;
  } catch (error) {
    pendingRequest = null;
    throw new Error(`Failed to encode query: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

export { encodeQueryToVector };