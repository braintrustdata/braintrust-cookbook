import os
import tempfile
from typing import Any, Dict

import braintrust
import openai
import requests
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

# Load your Braintrust API key from environment (or replace with your key string directly)
BRAINTRUST_API_KEY = os.getenv("BRAINTRUST_API_KEY")  # ensure this is set


# Initialize a Braintrust project (or get existing project)
project = braintrust.projects.create(name="Audio Translator")

transcription_prompt = project.prompts.create(
    name="Audio Translator",
    slug="audio-translator",
    description="Translate audio using GPT-4o",
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": (
                "You are an expert translation assistant. "
                "The user will provide an audio file path in their message. "
                "You can use the 'OpenAIWhisperTool' tool to transcribe it. "
                "Then accurately translate the transcribed text into Spanish. "
                "Return both the original transcription and the Spanish translation."
            )
        },
        {
            "role": "user",
            "content": "{{audio_path}}"
        }
    ],
    if_exists="replace"
)

# --------------------------------------------------------
# 3. OpenAI Whisper API Transcribe Function
# --------------------------------------------------------

# Make sure openai.api_key is set or use environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def openai_whisper_transcribe(audio_source: str) -> str:
    """
    Transcribe audio using OpenAI Audio.transcribe (old API pre-1.0).
    Accepts either:
      - A local file path (e.g., 'path/to/audio.wav'), or
      - A remote URL (e.g., 'https://.../audio.mp3').

    Steps:
      1. If audio_source is a URL, download it to a temp file.
      2. Otherwise, treat it as a local path.
      3. Call openai.Audio.transcribe(model='whisper-1').
      4. Return the transcribed text.

    This function requires openai==0.28.x or older, as newer versions removed Audio.transcribe.
    """
    temp_path = None
    # 1) Check if it's a URL or a local path
    if audio_source.startswith(("http://", "https://")):
        try:
            resp = requests.get(audio_source, stream=True)
            resp.raise_for_status()  # raise error if download fails
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download audio from URL: {e}")

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            tmp_file.write(resp.content)
            temp_path = tmp_file.name
        audio_path = temp_path
    else:
        # It's a local file path
        audio_path = audio_source
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        # 2) Transcribe using the old Audio.transcribe method
        with open(audio_path, "rb") as af:
            # 'Audio.transcribe' returns a dict with {"text": ...}
            result = openai.Audio.transcribe(
                model="whisper-1",
                file=af
            )
        transcript_text = result.get("text", "")
        if not transcript_text:
            raise RuntimeError(f"Empty transcription response: {result}")
        return transcript_text
    finally:
        # 3) Cleanup temp file if used
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# --------------------------------------------------------
# 4. Braintrust Tool for Transcription
# --------------------------------------------------------

class TranscriberParams(BaseModel):
    audio_path: str

class TranscriptionResult(BaseModel):
    text: str


# This tool calls the OpenAI Whisper API. Braintrust still sees it as a "tool"
# but it won't install local whisper/torch, since we're just making an HTTP request.
transcribe_tool = project.tools.create(
    name="OpenAIWhisperTool",
    slug="openai-whisper-tool",
    description="Transcribe audio file to text using OpenAI Whisper API",
    parameters=TranscriberParams,
    returns=TranscriptionResult,                        # A JSON schema describing the return type
    handler=openai_whisper_transcribe,
    if_exists="replace"                                # Overwrite if this slug already exists
)
