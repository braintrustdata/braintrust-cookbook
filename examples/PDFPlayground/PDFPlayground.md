# Using PDF Files in the Playground 
Adding attachments to Braintrust logs is great for capturing images, PDFs, or other files for your users, but what if you want to add those logs to a dataset and test them in the Braintrust Playground? In this cookbook we will show you how to run prompts in the Playground with files in three separate ways. 

The three methods:
- attach file via paperclip UI button
- Public URL  
- Base64 values  

You’ll learn how to:
- Emit spans with embedded file attachments  
- Log system prompts and user prompts into seperate spans in the same trace
- Save spans to a dataset  
- “Try Prompt” from a span and bring it into the Playground
- Use files in the playground for quick prompt iteration

For this example we will be using Earning Report transcript PDFs with a system prompt to analyze them.

## Getting Started
To setup your API keys:
- Create Braintrust account and create an API key.
- Create a .env.local file and add the API key (BRAINTRUST_API_KEY=...).
- Plug in your OpenAI API key in the settings page.
That's it! Now you can use your Braintrust API key to access OpenAI (and other AI providers), as well as log completions, run evals, and create prompts.

### Installing TS Dependencies
Install [pnpm](https://pnpm.io/installation) or a package manager of your choice. 

Set your package.json file as:
```json
{
	"name": "pdf-attachment-demo",
	"version": "1.0.0",
	"description": "PDF Attachment Demo",
	"scripts": {
		"logging": "ts-node simulate_logging.ts"
	},
	"devDependencies": {
		"@types/node": "^22.15.14",
		"@types/dotenv": "^8.2.0",
		"ts-node": "^10.9.2",
		"typescript": "^5.4.2"
	},
	"dependencies": {
		"dotenv": "^16.1.4",
		"braintrust": "^0.0.201",
		"openai": "^4.97.0"
	}
}
```

Then, run:
```bash
pnpm install
```

This will populate a node_modules directory with our dependencies!

## Building the simulate_logging.ts file
### Setting up our Braintrust and OpenAI clients

```typescript
import { initLogger, wrapOpenAI, wrapTraced, currentSpan, Attachment } from "braintrust";
import { OpenAI } from "openai";
import dotenv from 'dotenv';
dotenv.config();

// ── Braintrust + OpenAI setup ────────────────────────────────────────────────
const logger = initLogger({
    projectName: "pdf-attachment-demo",
    apiKey: process.env.BRAINTRUST_API_KEY,
});

const client = wrapOpenAI(
    new OpenAI({
        baseURL: "https://braintrustproxy.com/v1",
        apiKey: process.env.BRAINTRUST_API_KEY,
    }),
);
```

### PDF list to fetch
We can set a list of example pdfs for our code to fetch. This includes a public_url that will be used to download the pdf.

```typescript
// ── PDF list with URLs ────────────────────────────────────────────────
const pdfFiles = [
    { filename: "META-Q4-2024-Earnings-Call-Transcript.pdf", url: "https://s21.q4cdn.com/399680738/files/doc_financials/2024/q4/META-Q4-2024-Earnings-Call-Transcript.pdf" },
    { filename: "walmart-q4-fy25-earnings-call-transcript.pdf", url: "https://corporate.walmart.com/content/dam/corporate/documents/newsroom/2025/02/20/walmart-releases-q4-fy25-earnings/q4-fy25-earnings-call-transcript.pdf" },
    { filename: "Citi-4Q24-Earnings-Transcript.pdf", url: "https://www.citigroup.com/rcs/citigpa/storage/public/Earnings/Q42024/4Q24-Earnings-Transcript.pdf" },
    { filename: "jpmc-4q24-earnings-transcript.pdf", url: "https://www.jpmorganchase.com/content/dam/jpmc/jpmorgan-chase-and-co/investor-relations/documents/quarterly-earnings/2024/4th-quarter/4q24-earnings-transcript.pdf" },
    { filename: "att-4q24-transcript.pdf", url: "https://investors.att.com/~/media/Files/A/ATT-IR-V2/financial-reports/quarterly-earnings/2024/4Q24/t-usq-transcript-2025-01-27.pdf" },
    { filename: "Qualcomm_Q1FY25EC_Transcript_2-5-24.pdf", url: "https://s204.q4cdn.com/645488518/files/doc_events/2025/Feb/05/QCOM_Q1FY25EC_Transcript_2-5-24.pdf" },
    { filename: "host-hotels-4q24-transcript.pdf", url: "https://www.hosthotels.com/-/media/HostHotels/Files/DownloadLinksAssets/Earnings-Call-Transcript/Host_Hotels_Resorts_Inc_Earnings_Call_Transcript.pdf" },
    { filename: "homedepot-4q24-transcript.pdf", url: "https://ir.homedepot.com/~/media/Files/H/HomeDepot-IR/documents/hd-4q24-transcript.pdf" },
];
```

### Define the System Prompt

```typescript
// ── System prompt for the assistant ─────────────────────────────────────────────
const SYSTEM_PROMPT = `
You are a financial analyst specializing in earnings call analysis. Your task is to provide a quick, bullet-point summary of the key points from earnings call transcripts.

Focus ONLY on these 3-5 key points:
• Revenue and EPS figures vs expectations
• Major business highlights or challenges
• Forward guidance for next quarter

Keep each point to 1-2 sentences maximum. Be extremely concise and focus only on the most important information.
Only output the key points, no other text.
`;
```

### Function to process each PDF

```typescript
// ── Helper function to process a single PDF ────────────────────────────────
const processPdf = wrapTraced(async (pdfFile: { filename: string; url: string }) => {
    console.log(`Processing ${pdfFile.filename}...`);

    // Fetch and encode the PDF file from URL (with error handling)
    let pdfData: Buffer;
    let base64String: string;
    try {
        const response = await fetch(pdfFile.url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status} ${response.statusText}`);
        }
        const arrayBuffer = await response.arrayBuffer();
        pdfData = Buffer.from(arrayBuffer);
        base64String = pdfData.toString('base64');
    } catch (err: any) {
        console.error(`Failed to download ${pdfFile.url}:`, err);
        return; // Skip this PDF and continue with the next
    }

    const userPrompt = "Please analyze this earnings call transcript";
    const rootSpan = currentSpan();
    rootSpan.setAttributes({ name: pdfFile.filename });
    const rootSpanSlug = currentSpan().export();
    
    // Create chat completion with file data
    const completion = await client.chat.completions.create({
        model: "gpt-4o",
        messages: [
            {
                role: "system",
                content: SYSTEM_PROMPT
            },
            {
                role: "user",
                content: [
                    {
                        type: "file",
                        file: {
                            filename: pdfFile.filename,
                            file_data: `data:application/pdf;base64,${base64String}`
                        }
                    },
                    {
                        type: "text",
                        text: userPrompt
                    }
                ]
            }
        ],
        max_tokens: 500
    });

    const summary = completion.choices[0]?.message?.content;

    // if no summary is generated, log an error and return
    if (!summary) {
        console.warn("No summary generated");
        return;
    }
    // Console log that the summary was created
    console.log(`\nEarnings Summary for ${pdfFile.filename}: Summary Created! View in the Braintrust UI!\n`);

    // log the output of the LLM call to the root span
    rootSpan.log({
        output: summary
    });

    // Log system prompt span
    await logSystemPrompt(pdfFile.filename, pdfFile.url, summary, rootSpanSlug);

    // Log user prompt span
    await logUserPrompt(pdfFile.filename, pdfFile.url, userPrompt, summary, rootSpanSlug, base64String);
    
}, logger);
```

### System Span Function

```typescript
// ── Helper function to log system prompt span ──────────────────────────────
async function logSystemPrompt(filename: string, url: string, summary: string, rootSpan: Promise<string>) {
    const systemSpan = wrapTraced(async () => {
        const span = currentSpan();
        span.setAttributes({ 
            name: "system_prompt", 
            type: "llm", 
            parent: (await rootSpan).toString()
        });
        
        span.log({
            input: [{
                role: "system",
                content: SYSTEM_PROMPT
            }],
            output: summary
        });
    }, logger);
    await systemSpan();
}
```

### User Span Function

```typescript
// ── Helper function to log user prompt span ───────────────────────────
async function logUserPrompt(filename: string, url: string, userPrompt: string, summary: string, rootSpan: Promise<string>, base64String: string) {
    const userPromptSpan = wrapTraced(async () => {
        const span = currentSpan();
        span.setAttributes({ 
            name: "user_prompt", 
            type: "llm", 
            parent: (await rootSpan).toString()
        });
        
        // Reconstruct PDF data from base64
        const pdfData = Buffer.from(base64String, 'base64');

        const attachment = new Attachment({
            data: pdfData,                       
            filename,
            contentType: "application/pdf",
          });
        
        span.log({
            input: [
                { role: "user", content: userPrompt },
            ],
            output: summary,
            metadata: {
                filename,
                url,
                base64String,
                attachment
            }
        });
    }, logger);
    await userPromptSpan();
}
```

### Putting it all together

```typescript
// ── Main function to process all PDFs ─────────────────────────────────────
const generateSummary = async () => {
    console.log(`Found ${pdfFiles.length} PDFs to process`);

    try {
        for (const pdfFile of pdfFiles) {
            await processPdf(pdfFile);
        }
    } catch (err: any) {
        console.error("Error in main:", err);
        if (err?.response?.data) {
            console.error("Response data:", err.response.data);
        }
    }
};

generateSummary();
```
### Run the simulate_logging.ts file
```bash
pnpm logging
or
pnpm ts-node simulate_logging.ts
```

## Now we move to the Braintrust UI

### Adding User Prompt Spans to a Dataset
We want to save the user spans for the 8 pdf traces we have logged into a dataset called "pdf-dataset"

![add span to dataset](./assets/add-span-to-dataset.gif)

You can use the D hotkey (add span to dataset) to speed this up

### Adding System Prompt Span to Library & Opening Playground
In the system_prompt span in a trace (doesn't matter which one as they're all the same) click on the "Try prompt" button in the top right.

Name the prompt "system1" and click the button to "Save as custom prompt"

Now click on the button "Create playground with prompt"

![try prompt from span](./assets/try-prompt.gif)

### Test the various methods of adding files in the playground!
Create another prompt in the playground by clicking on "Task" > "Prompt" > "system1"

You now have two prompts that are exactly the same in the playground.

Before setting up the base64 and public url methods I want to show you how to click on the paperclip attachment and add a file manually.

In a prompt click on "+ Message" to add a user prompt. Now click on "+ Message Part" > "File"

This will now reveal a paperclip icon on the right side that once clicked will let you attach files from your local machine.

![Duplicate prompt & paperclip](./assets/paperclip.gif)

Now that you know that is an option, let's cover the other two methods:
- base64 values
- public url

{insert gif of both prompts side by side with base64 and public url}

[add information of base64 and public url limitations]

