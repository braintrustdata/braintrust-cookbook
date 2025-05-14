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

// ── PDF list with URLs ────────────────────────────────────────────────
const pdfFiles = [
    { filename: "META-Q4-2024-Earnings-Call-Transcript.pdf", url: "https://s21.q4cdn.com/399680738/files/doc_financials/2024/q4/META-Q4-2024-Earnings-Call-Transcript.pdf" },
    { filename: "Citi-4Q24-Earnings-Transcript.pdf", url: "https://www.citigroup.com/rcs/citigpa/storage/public/Earnings/Q42024/4Q24-Earnings-Transcript.pdf" },
    { filename: "jpmc-4q24-earnings-transcript.pdf", url: "https://www.jpmorganchase.com/content/dam/jpmc/jpmorgan-chase-and-co/investor-relations/documents/quarterly-earnings/2024/4th-quarter/4q24-earnings-transcript.pdf" },
    { filename: "att-4q24-transcript.pdf", url: "https://investors.att.com/~/media/Files/A/ATT-IR-V2/financial-reports/quarterly-earnings/2024/4Q24/t-usq-transcript-2025-01-27.pdf" },
    { filename: "Qualcomm_Q1FY25EC_Transcript_2-5-24.pdf", url: "https://s204.q4cdn.com/645488518/files/doc_events/2025/Feb/05/QCOM_Q1FY25EC_Transcript_2-5-24.pdf" },
    { filename: "host-hotels-4q24-transcript.pdf", url: "https://www.hosthotels.com/-/media/HostHotels/Files/DownloadLinksAssets/Earnings-Call-Transcript/Host_Hotels_Resorts_Inc_Earnings_Call_Transcript.pdf" },
    { filename: "homedepot-4q24-transcript.pdf", url: "https://ir.homedepot.com/~/media/Files/H/HomeDepot-IR/documents/hd-4q24-transcript.pdf" },
];

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

// ── Helper function to log system prompt span ──────────────────────────────
async function logSystemPrompt( summary: string, rootSpan: Promise<string>) {
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