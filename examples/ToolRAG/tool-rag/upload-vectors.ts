import fs from "fs";
import path from "path";
import dotenv from "dotenv";
import { marked } from "marked";
import { OpenAI } from "openai";
import { MongoClient } from "mongodb";
import { EMBEDDING_MODEL, UPLOAD_BATCH_SIZE } from "./constants";

interface Section {
  title: string;
  content: string;
}

interface DocType {
  _id: string;
  title: string;
  content: string;
  embedding: number[];
}

dotenv.config({ path: ".env.local" });

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

function parseMarkdownFile(filePath: string): Section[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const tokens = marked.lexer(content);
  const sections: Section[] = [];
  let currentSection: Section | null = null;

  tokens.forEach((token) => {
    if (token.type === "heading") {
      if (currentSection) {
        sections.push(currentSection);
      }
      currentSection = {
        title: token.text,
        content: "",
      };
    } else if (currentSection) {
      if (token.type === "paragraph" || token.type === "text") {
        currentSection.content += token.text + "\n";
      } else if (token.type === "code") {
        currentSection.content +=
          "```" + token.lang + "\n" + token.text + "\n```\n";
      }
    }
  });

  if (currentSection) {
    sections.push(currentSection);
  }

  for (let i = 0; i < sections.length - 1; i++) {
    if (sections[i].title !== "" && sections[i].content === "") {
      sections[i].content =
        sections[i + 1].title + "\n" + sections[i + 1].content;
      sections[i + 1].title = "";
      sections[i + 1].content = "";
    }
  }

  return sections.filter((section) => section.content !== "");
}

function getAllMarkdownFiles(dirPath: string): string[] {
  const files: string[] = [];
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...getAllMarkdownFiles(fullPath));
    } else if (
      entry.isFile() &&
      (entry.name.endsWith(".md") || entry.name.endsWith(".mdx"))
    ) {
      files.push(fullPath);
    }
  }

  return files;
}

async function createEmbeddingWithRetry(input, retries = 3, delayMs = 1000) {
  for (let i = 0; i < retries; i++) {
    try {
      return await openai.embeddings.create({ input, model: EMBEDDING_MODEL });
    } catch (error) {
      if (error.response?.status === 429 && i < retries - 1) {
        console.log(`Rate limited. Retrying after ${delayMs}ms...`);
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      } else {
        throw error;
      }
    }
  }
}

async function main() {
  await client.connect();
  const db = client.db("braintrust-docs");
  const collection = db.collection<DocType>("documents");

  const docsDir = path.join(__dirname, "docs-sample");
  const markdownFiles = getAllMarkdownFiles(docsDir);

  const allSections: Section[] = [];

  for (const file of markdownFiles) {
    const sections = parseMarkdownFile(file);
    allSections.push(...sections);
  }

  const upserts = [];
  for (let i = 0; i < allSections.length; i += UPLOAD_BATCH_SIZE) {
    const batch = allSections.slice(i, i + UPLOAD_BATCH_SIZE);

    const batchPromises = batch.map(async (item, j) => {
      const embeddingResponse = await createEmbeddingWithRetry(
        `# ${item.title}\n\n${item.content}`
      );

      const embedding = embeddingResponse.data[0].embedding;

      return collection.updateOne(
        { _id: `${item.title}-${i * UPLOAD_BATCH_SIZE + j}` },
        {
          $set: {
            title: item.title,
            content: item.content,
            embedding: embedding,
          },
        },
        { upsert: true }
      );
    });

    upserts.push(...batchPromises);

    // Throttle requests by awaiting each batch
    await Promise.all(upserts);
  }

  console.log(`Uploaded ${allSections.length} documents.`);
}

main()
  .catch(console.error)
  .finally(() => client.close());
