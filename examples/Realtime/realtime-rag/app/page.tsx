import { ConsolePage } from '@/components/ConsolePage';
import './App.scss';

const PROXY_URL =
  process.env.BRAINTRUST_PROXY_URL ?? 'https://braintrustproxy.com/v1';

// You can swap this out to your OPENAI_API_KEY if you do not have a Braintrust account, but
// you will not have access to logging features.
const API_KEY = process.env.BRAINTRUST_API_KEY;

// Set this to your project name if you have one, otherwise it will default to "Realtime voice console"
const BRAINTRUST_PROJECT_NAME = process.env.BRAINTRUST_PROJECT_NAME;

export default async function Home() {
  if (!API_KEY) {
    return (
      <div>
        No API key configured server-side. Please set BRAINTRUST_API_KEY
      </div>
    );
  }

  const model = 'gpt-4o-realtime-preview-2024-10-01';
  const response = await fetch(`${PROXY_URL}/credentials`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model,
      logging: {
        project_name: BRAINTRUST_PROJECT_NAME || "Realtime RAG bot",
      },
      // This is the TTL for starting the conversation, but it can continue as long as needed
      // once the conversation is started.
      ttl_seconds: 60 * 10 /* 10 minutes */,
    }),
    cache: 'no-store',
  });

  if (!response.ok) {
    const text = await response.text();
    return <div><p>Failed to get credentials</p><pre>{text}</pre></div>;
  }

  const { key } = await response.json();

  return <ConsolePage apiKey={key} url={`${PROXY_URL}/realtime`} />;
}
