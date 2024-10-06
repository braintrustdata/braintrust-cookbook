import fs from "fs";
import path from "path";
import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkMdx from "remark-mdx";
import { visit } from "unist-util-visit";

interface Section {
  title: string;
  content: string;
}

function parseMarkdownFile(filePath: string): Section[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const sections: Section[] = [];
  let currentSection: Section | null = null;

  const tree = unified().use(remarkParse).use(remarkMdx).parse(content);

  visit(tree, ["heading", "text"], (node) => {
    if (node.type === "heading") {
      if (currentSection) {
        sections.push(currentSection);
      }
      currentSection = {
        title: "",
        content: "",
      };
    }

    if (currentSection) {
      if (node.type === "heading") {
        currentSection.title += (node.children[0] as any).value;
      } else if (node.type === "text") {
        currentSection.content += node.value + "\n";
      }
    }
  });

  if (currentSection) {
    sections.push(currentSection);
  }

  return sections;
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

async function main() {
  const docsDir = path.join(__dirname, "docs-sample");
  const markdownFiles = getAllMarkdownFiles(docsDir);
  console.log(markdownFiles);

  // const allSections: Section[] = [];

  // for (const file of markdownFiles) {
  //   const sections = parseMarkdownFile(file);
  //   allSections.push(...sections);
  // }
}

main().catch(console.error);
