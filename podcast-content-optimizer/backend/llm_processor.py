import os
import json
import logging
import time
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
from utils import parse_duration, format_duration  # Changed from utils.time_utils

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME")
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
    prompt = load_prompt('openai')

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
                "content": f"{prompt}\n\n{transcript}"
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
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    prompt = load_prompt('gemini')

    full_prompt = f"{prompt}\n\n{transcript}"
    logging.info(f"Sending prompt to Gemini (first 500 characters): {full_prompt[:500]}...")
    start_time = time.time()
    response = model.generate_content(
        full_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    end_time = time.time()
    logging.info(f"Gemini response received in {end_time - start_time:.2f} seconds")
    logging.info(f"Gemini response (first 500 characters): {response.text[:500]}...")
    return response.text

import ast

def parse_llm_response(llm_response):
    logging.info("Parsing LLM response")
    logging.info(f"Raw LLM response (first 1000 characters): {llm_response[:1000]}")

    if isinstance(llm_response, dict):
        logging.info(f"LLM response is already a dict. Found {len(llm_response.get('unwanted_content', []))} segments.")
        return llm_response

    try:
        # First, try to parse as JSON
        parsed_content = json.loads(llm_response)
    except json.JSONDecodeError:
        logging.info("JSON parsing failed, attempting to use ast.literal_eval")
        try:
            # If JSON parsing fails, try using ast.literal_eval
            parsed_content = ast.literal_eval(llm_response)
        except (SyntaxError, ValueError) as e:
            logging.error(f"ast.literal_eval parsing failed. Error: {str(e)}")
            # If both methods fail, attempt to extract JSON-like content
            import re
            json_pattern = r'\[.*?\]'
            match = re.search(json_pattern, llm_response, re.DOTALL)
            if match:
                logging.info("Found JSON-like content using regex")
                try:
                    parsed_content = ast.literal_eval(match.group())
                except (SyntaxError, ValueError) as e:
                    logging.error(f"Failed to parse extracted JSON-like content. Error: {str(e)}")
                    logging.error(f"LLM response content: {llm_response}")
                    return {"unwanted_content": []}
            else:
                logging.error("No JSON-like content found in LLM response")
                logging.error(f"LLM response content: {llm_response}")
                return {"unwanted_content": []}

    logging.info(f"Successfully parsed LLM response. Type: {type(parsed_content)}")

    # Handle both array and dict with single key scenarios
    if isinstance(parsed_content, list):
        logging.info(f"Parsed content is a list. Found {len(parsed_content)} segments.")
        unwanted_content = parsed_content
    elif isinstance(parsed_content, dict) and len(parsed_content) == 1:
        key = next(iter(parsed_content))
        unwanted_content = parsed_content[key]
        logging.info(f"Parsed content is a dict with key '{key}'. Found {len(unwanted_content)} segments.")
    else:
        raise ValueError(f"Unexpected parsed content type: {type(parsed_content)}")

    # Convert any time format to seconds
    for segment in unwanted_content:
        segment['start_time'] = parse_duration(segment['start_time'])
        segment['end_time'] = parse_duration(segment['end_time'])

    logging.info(f"Final unwanted content (first 3 segments): {unwanted_content[:3]}")
    return {"unwanted_content": unwanted_content}
