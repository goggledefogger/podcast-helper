import os
import json
import logging
import time
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

def find_unwanted_content(transcript_file_path):
    logging.info(f"Starting unwanted content detection for file: {transcript_file_path}")
    with open(transcript_file_path, "r") as file:
        transcript = file.read()

    logging.info(f"Transcript length: {len(transcript)} characters")

    if LLM_PROVIDER == "openai":
        llm_response = process_with_openai(transcript)
    elif LLM_PROVIDER == "gemini":
        llm_response = process_with_gemini(transcript)
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

    parsed_response = parse_llm_response(llm_response)
    logging.info(f"Found {len(parsed_response['unwanted_content'])} unwanted content segments")
    return parsed_response

def process_with_openai(transcript):
    logging.info("Processing with OpenAI")
    client = OpenAI(api_key=OPENAI_API_KEY)
    start_time = time.time()
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
    end_time = time.time()
    logging.info(f"OpenAI response received in {end_time - start_time:.2f} seconds")
    return response.choices[0].message.content

def process_with_gemini(transcript):
    logging.info("Processing with Gemini")
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
    prompt = (
        "Here is a transcript, please identify the start and end times of sections that contain unwanted content.\n" +
        "Provide the output as a JSON array where each object has 'start_time', 'end_time', and 'description' keys.\n" +
        "Example format: [{'start_time': '00:10:15', 'end_time': '00:12:45', 'description': 'Unwanted content 1'}].\n" +
        "Here is the transcript:\n\n" +
        f"{transcript}"
    )
    logging.info(f"Sending prompt to Gemini (first 500 characters): {prompt[:500]}...")
    start_time = time.time()
    response = model.generate_content(prompt)
    end_time = time.time()
    logging.info(f"Gemini response received in {end_time - start_time:.2f} seconds")
    logging.info(f"Gemini response (first 500 characters): {response.text[:500]}...")
    return response.text

def parse_llm_response(llm_response):
    logging.info("Parsing LLM response")
    if isinstance(llm_response, dict):
        # If llm_response is already a dict, return it directly
        logging.info(f"LLM response is already a dict. Found {len(llm_response.get('unwanted_content', []))} segments.")
        return llm_response
    try:
        # Attempt to parse the response as JSON
        unwanted_content = json.loads(llm_response)
        if isinstance(unwanted_content, list):
            logging.info(f"Successfully parsed LLM response. Found {len(unwanted_content)} segments.")
            return {"unwanted_content": unwanted_content}
        elif isinstance(unwanted_content, dict):
            logging.info(f"Successfully parsed LLM response. Found {len(unwanted_content.get('unwanted_content', []))} segments.")
            return unwanted_content
        else:
            raise ValueError("LLM response is not a list or dict")
    except json.JSONDecodeError:
        # If JSON parsing fails, attempt to extract JSON-like content
        import re
        json_pattern = r'\[.*?\]'
        match = re.search(json_pattern, llm_response, re.DOTALL)
        if match:
            try:
                unwanted_content = json.loads(match.group())
                logging.info(f"Extracted and parsed JSON-like content. Found {len(unwanted_content)} segments.")
                return {"unwanted_content": unwanted_content}
            except json.JSONDecodeError:
                logging.error("Failed to parse extracted JSON-like content")
        else:
            logging.error("No JSON-like content found in LLM response")

    # If all parsing attempts fail, return an empty list
    logging.warning("Returning empty list due to parsing failure")
    return {"unwanted_content": []}
