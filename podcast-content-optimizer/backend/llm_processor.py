import os
import json
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

def find_unwanted_content(transcript_file_path):
    logging.info("Starting unwanted content detection")
    with open(transcript_file_path, "r") as file:
        transcript = file.read()

    logging.info(f"Transcript length: {len(transcript)} characters")

    if LLM_PROVIDER == "openai":
        return process_with_openai(transcript)
    elif LLM_PROVIDER == "gemini":
        return process_with_gemini(transcript)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

def process_with_openai(transcript):
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo-16k",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that helps find unwanted content in transcripts."
            },
            {
                "role": "user",
                "content": (
                    "Here is a transcript, please identify the start and end times of sections that contain unwanted content.\n" +
                    "Provide the output as a JSON array where each object has 'start_time', 'end_time', and 'description' keys.\n" +
                    "Example format: [{'start_time': '00:10:15', 'end_time': '00:12:45', 'description': 'Unwanted content 1'}].\n" +
                    "Here is the transcript:\n\n" +
                    f"{transcript}"
                )
            }
        ],
        max_tokens=16000
    )
    return response.choices[0].message.content

def process_with_gemini(transcript):
    # Implement Gemini processing here
    pass
