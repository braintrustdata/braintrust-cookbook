import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import matter from "gray-matter";

// A single judgeable behavior: one "## ..." section of the BEHAVIOR.md body.
export interface BehaviorSection {
  title: string;
  slug: string;
  // The full section text (heading + prose) handed to the judge as the rubric.
  body: string;
}

export interface BehaviorSpec {
  name: string;
  description: string;
  // The complete Markdown body, minus frontmatter.
  body: string;
  // One entry per "## " behavior in the spec.
  sections: BehaviorSection[];
  location: string;
}

const DEFAULT_SPEC_URL = new URL(
  "./.agents/behaviors/verify-before-done/BEHAVIOR.md",
  import.meta.url,
);

function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Split the body into one section per "## " heading. Everything above the first
// "## " (the H1 and any agent overview) is preamble and is not judged on its own.
function splitSections(body: string): BehaviorSection[] {
  const lines = body.split("\n");
  const sections: BehaviorSection[] = [];
  let current: { title: string; lines: string[] } | null = null;

  for (const line of lines) {
    const match = /^##\s+(.+?)\s*$/.exec(line);
    if (match) {
      if (current) sections.push(finalize(current));
      current = { title: match[1], lines: [line] };
    } else if (current) {
      current.lines.push(line);
    }
  }
  if (current) sections.push(finalize(current));

  return sections;

  function finalize(section: { title: string; lines: string[] }): BehaviorSection {
    return {
      title: section.title,
      slug: slugify(section.title),
      body: section.lines.join("\n").trim(),
    };
  }
}

// Load and parse a BEHAVIOR.md spec. In production, validate specs with the
// `agentbehavior` CLI (https://github.com/braintrustdata/agentbehavior); here we
// parse just enough to drive the eval.
export function loadBehaviorSpec(specUrl: URL = DEFAULT_SPEC_URL): BehaviorSpec {
  const location = fileURLToPath(specUrl);
  const raw = readFileSync(location, "utf8");
  const { data, content } = matter(raw);

  const name = typeof data.name === "string" ? data.name : "";
  const description = typeof data.description === "string" ? data.description : "";
  if (name.length === 0 || description.length === 0) {
    throw new Error(`Spec at ${location} is missing a name or description in its frontmatter.`);
  }

  const sections = splitSections(content);
  if (sections.length === 0) {
    throw new Error(`Spec at ${location} has no "## " behavior sections to judge.`);
  }

  return { name, description, body: content.trim(), sections, location };
}
