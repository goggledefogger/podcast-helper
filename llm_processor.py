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
    logging.info("Using Gemini for processing")
    genai.configure(api_key=GOOGLE_API_KEY)

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro-latest",
        generation_config={
            "temperature": 0.2,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json"
        }
    )

    json_schema = {
        "title": "Unwanted Content in Podcast Transcript",
        "description": "Identify sections of unwanted content in the podcast transcript",
        "type": "object",
        "properties": {
            "unwanted_content": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "Start time of unwanted content in HH:MM:SS format"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "End time of unwanted content in HH:MM:SS format"
                        },
                        "description": {
                            "type": "string",
                            "description": "Brief description of the unwanted content"
                        }
                    },
                    "required": ["start_time", "end_time", "description"]
                }
            }
        },
        "required": ["unwanted_content"]
    }

    prompt = (f"Follow JSON schema.<JSONSchema>{json.dumps(json_schema)}</JSONSchema>\n\n"
              f"Analyze the following transcript and identify unwanted content according to the schema:\n\n{transcript}")

    try:
        response = model.generate_content(prompt)

        logging.info("Received response from Gemini")
        json_output = response.text
        logging.info(f"Raw response from Gemini: {json_output}")

        return json_output

    except Exception as e:
        logging.error(f"Error in Gemini processing: {str(e)}")
        raise

# Add this function to parse and validate the LLM response
def parse_llm_response(llm_response):
    try:
        logging.info("Attempting to parse LLM response as JSON")
        unwanted_content_data = json.loads(llm_response)
        if "unwanted_content" in unwanted_content_data:
            unwanted_content_list = unwanted_content_data["unwanted_content"]
            logging.info(f"Successfully parsed JSON. Found {len(unwanted_content_list)} unwanted content sections")
            return unwanted_content_data
        else:
            raise ValueError("Expected 'unwanted_content' key not found in JSON response")
    except (json.JSONDecodeError, ValueError) as e:
        logging.error(f"Error parsing JSON: {e}")
        logging.error(f"Raw LLM response: {llm_response}")
        raise
