import { NextResponse } from 'next/server';
import { Pinecone } from '@pinecone-database/pinecone';
import dotenv from 'dotenv';
import path from 'path';
import { encodeQueryToVector } from '@/lib/ragtool/vectorEncoder';

dotenv.config({ path: path.resolve(process.cwd(), '.env') });

if (!process.env.PINECONE_API_KEY) {
  throw new Error('PINECONE_API_KEY is not set');
}

async function retrieveFromPinecone(query: string) {
  const pinecone = new Pinecone({ apiKey: process.env.PINECONE_API_KEY });
  const index = pinecone.Index('braintrust-docs');
  const vector = await encodeQueryToVector(query);

  const result = await index.query({
    vector,
    topK: 5,
    includeMetadata: true,
  });

  return result.matches.map((match) => ({
    id: match.id,
    score: match.score,
    metadata: match.metadata,
  }));
}

export async function POST(req: Request) {
  try {
    const { query } = await req.json();

    if (!query) {
      return NextResponse.json({ error: 'Query is required' }, { status: 400 });
    }

    const results = await retrieveFromPinecone(query);
    return NextResponse.json({ results }, { status: 200 });
  } catch (error) {
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}