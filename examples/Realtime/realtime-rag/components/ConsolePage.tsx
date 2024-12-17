'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { RealtimeClient } from '@openai/realtime-api-beta';
import { ItemType } from '@openai/realtime-api-beta/dist/lib/client.js';
import { WavRecorder, WavStreamPlayer } from '../lib/wavtools/index.js';
import { instructions } from '../utils/conversation_config.js';
import { X, Mic } from 'react-feather';
import { Button } from '../components/button/Button';
import './ConsolePage.scss';
import ReactMarkdown from 'react-markdown';
import React from 'react';

interface PineconeResult {
  id: string;
  score: number;
  metadata: {
    title: string;
    content: string;
  };
}

async function fetchFromPinecone(query: string): Promise<PineconeResult[]> {
  const response = await fetch('/api/retrievePinecone', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch from Pinecone: ${response.statusText}`);
  }

  const { results } = await response.json();
  return results;
}

export function ConsolePage({ apiKey, url }: { apiKey: string; url: string }) {
  const wavRecorderRef = useRef<WavRecorder>(new WavRecorder({ sampleRate: 24000 }));
  const wavStreamPlayerRef = useRef<WavStreamPlayer>(new WavStreamPlayer({ sampleRate: 24000 }));
  const clientRef = useRef<RealtimeClient | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  if (!clientRef.current) {
    clientRef.current = new RealtimeClient({
      apiKey,
      url,
      dangerouslyAllowAPIKeyInBrowser: true,
    });
  }

  const [items, setItems] = useState<ItemType[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [canPushToTalk, setCanPushToTalk] = useState(true);
  const [isRecording, setIsRecording] = useState(false);
  const [memoryKv, setMemoryKv] = useState<{ [key: string]: any }>({});
  const [lastQuery, setLastQuery] = useState<string>('');
  const [retrievalResults, setRetrievalResults] = useState<PineconeResult[]>([]);
  const [hasHadConversation, setHasHadConversation] = useState(false);

  const scrollToBottom = () => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [items]);

  const connectConversation = useCallback(async () => {
    try {
      const client = clientRef.current;
      if (!client) throw new Error('Client is null');

      setIsConnected(true);
      setItems([]);
      setRetrievalResults([]);

      await wavRecorderRef.current.begin();
      await wavStreamPlayerRef.current.connect();
      await client.connect();
      await client.sendUserMessageContent([{ type: 'input_text', text: 'Hello!' }]);

      setItems([...client.conversation.getItems()]);
    } catch (error) {
      setIsConnected(false);
    }
  }, []);

  const disconnectConversation = useCallback(async () => {
    try {
      setIsConnected(false);
      setHasHadConversation(true);

      const client = clientRef.current;
      if (!client) throw new Error('Client is null');

      await client.disconnect();
      await wavRecorderRef.current.end();
      await wavStreamPlayerRef.current.interrupt();
    } catch (error) {
      setIsConnected(false);
    }
  }, []);

  const startRecording = async () => {
    try {
      setIsRecording(true);
      const client = clientRef.current;
      if (!client) throw new Error('Client is null');

      const wavStreamPlayer = wavStreamPlayerRef.current;
      const trackSampleOffset = await wavStreamPlayer.interrupt();
      
      if (trackSampleOffset?.trackId) {
        const { trackId, offset } = trackSampleOffset;
        await client.cancelResponse(trackId, offset);
        setItems([...client.conversation.getItems()]);
      }

      await wavRecorderRef.current.record(async (data) => {
        await client.appendInputAudio(data.mono);
      });
    } catch (error) {
      setIsRecording(false);
    }
  };

  const stopRecording = async () => {
    try {
      const client = clientRef.current;
      if (!client) throw new Error('Client is null');

      await wavRecorderRef.current.pause();
      setIsRecording(false);
      await client.createResponse();
    } catch (error) {
      setIsRecording(false);
    }
  };

  useEffect(() => {
    const client = clientRef.current;
    if (!client) return;

    client.updateSession({
      instructions,
      input_audio_transcription: { model: 'whisper-1' }
    });

    client.addTool(
      {
        name: 'set_memory',
        description: 'Saves important data about the user into memory.',
        parameters: {
          type: 'object',
          properties: {
            key: {
              type: 'string',
              description: 'The key of the memory value. Always use lowercase and underscores.',
            },
            value: {
              type: 'string',
              description: 'Value can be anything represented as a string',
            },
          },
          required: ['key', 'value'],
        },
      },
      async ({ key, value }: { key: string; value: string }) => {
        setMemoryKv(prev => ({ ...prev, [key]: value }));
        return { ok: true };
      }
    );

    client.addTool(
      {
        name: 'pinecone_retrieval',
        description: 'Retrieves relevant information from Braintrust documentation.',
        parameters: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'The search query to find relevant documentation.'
            }
          },
          required: ['query']
        },
      },
      async ({ query }: { query: string }) => {
        try {
          setLastQuery(query);
          const results = await fetchFromPinecone(query);
          setRetrievalResults(results);
          return results
            .map(result => `[Score: ${result.score.toFixed(2)}] ${result.metadata.title}\n${result.metadata.content}`)
            .join('\n\n');
        } catch (error) {
          throw error;
        }
      }
    );

    const handleConversationUpdate = async ({ item, delta }: { item: ItemType; delta: any }) => {
      try {    
        const wavStreamPlayer = wavStreamPlayerRef.current;
    
        if (delta?.audio) {
          await wavStreamPlayer.add16BitPCM(delta.audio, item.id);
    
          if (item.formatted.audio?.length) {
            const wavFile = await WavRecorder.decode(item.formatted.audio, 24000, 24000);
            item.formatted.file = wavFile;
          }
        }
    
        if (item.status === 'incomplete' && item.content?.length) {
          item.formatted.transcript = item.content[0]?.transcript || '...';
        }
    
        if (item.formatted.text || item.formatted.transcript || item.formatted.audio?.length) {
          setItems(clientRef.current?.conversation.getItems() || []);
        }
      } catch (error) {
        console.error('Error in handleConversationUpdate:', error);
      }
    };

    client.on('conversation.updated', handleConversationUpdate);
    client.on('error', console.error);

    return () => {
      client.off('conversation.updated', handleConversationUpdate);
      client.off('error', console.error);
      client.reset();
    };
  }, []);

  return (
    <div data-component="ConsolePage">
      <div className="chat-container">
        <header className="chat-header">
          <div className="header-content">
            <h1>Voice chat with Braintrust expert</h1>
          </div>
        </header>

        <div className="chat-main">
          <div className="messages-container" ref={messagesContainerRef}>
            {!items.length && !hasHadConversation ? (
              <div className="welcome-message">
                <p>Start the conversation to ask a question!</p>
              </div>
            ) : (
              items.map(item => {
                if (item.type === 'function_call_output' ||
                  (item.formatted.tool && item.formatted.tool.name === 'pinecone_retrieval')) {
                  return null;
                }
              
                return (
                  <div
                    key={item.id}
                    className={`message ${item.role === 'user' ? 'user' : 'assistant'}`}
                  >
                    <div className="message-content">
                      {!item.formatted.tool && item.role === 'user' && (
                        <p>
                          {item.formatted.transcript ||
                            item.formatted.text ||
                            item.content?.[0]?.transcript ||
                            (item.formatted.audio?.length && !item.formatted.transcript ? '...' : '')}
                        </p>
                      )}
              
                      {!item.formatted.tool && item.role === 'assistant' && (
                        <div className="message-content">
                          <ReactMarkdown>
                            {item.formatted.transcript ||
                              item.formatted.text ||
                              item.content?.[0]?.transcript ||
                              '...'}
                          </ReactMarkdown>
                        </div>
                      )}
                      {item.formatted.file && (
                        <audio
                          className="message-audio"
                          src={item.formatted.file.url}
                          controls
                        />
                      )}
                    </div>
                  </div>
                );
              })              
            )}
          </div>

          <div className="chat-controls">
            <div className="input-controls">
              {!isConnected ? (
                <Button
                  label={hasHadConversation ? "New Conversation" : "Start Conversation"}
                  icon={Mic}
                  buttonStyle="action"
                  className="start-button"
                  onClick={connectConversation}
                />
              ) : (
                <div className="active-controls">
                  <Button
                    icon={Mic}
                    label={isRecording ? 'Release to Send' : 'Hold to Talk'}
                    buttonStyle={isRecording ? 'alert' : 'action'}
                    className={`mic-button ${isRecording ? 'recording' : ''}`}
                    disabled={!canPushToTalk}
                    onMouseDown={startRecording}
                    onMouseUp={stopRecording}
                  />
                  <Button
                    icon={X}
                    buttonStyle="regular"
                    label="End Conversation"
                    onClick={disconnectConversation}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}