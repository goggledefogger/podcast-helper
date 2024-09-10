import os
import whisper
import subprocess
from dotenv import load_dotenv
import json
import google.generativeai as genai
from openai import OpenAI
import logging
import time
import sys
import threading
from pydub import AudioSegment

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

logging.info(f"Using LLM provider: {LLM_PROVIDER}")

PODCAST_URL = "https://pdst.fm/e/chrt.fm/track/479722/arttrk.com/p/CRMDA/claritaspod.com/measure/pscrb.fm/rss/p/pdrl.fm/b85a46/stitcher.simplecastaudio.com/9aa1e238-cbed-4305-9808-c9228fc6dd4f/episodes/807e8acc-db19-41cb-a5b4-a1258af36943/audio/128/default.mp3?aid=rss_feed&awCollectionId=9aa1e238-cbed-4305-9808-c9228fc6dd4f&awEpisodeId=807e8acc-db19-41cb-a5b4-a1258af36943&feed=dxZsm5kX"

# Animation function
def animate(stop_event):
    chars = "|/-\\"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write('\r' + 'Processing ' + chars[i % len(chars)])
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1

# Wrapper function to run a task with animation
def run_with_animation(task, *args, **kwargs):
    stop_event = threading.Event()
    animation_thread = threading.Thread(target=animate, args=(stop_event,))
    animation_thread.start()

    try:
        result = task(*args, **kwargs)
    finally:
        stop_event.set()
        animation_thread.join()
        sys.stdout.write('\r' + ' ' * 20 + '\r')  # Clear the animation line
        sys.stdout.flush()

    return result

def find_unwanted_content(transcript_file_path):
    logging.info("Starting unwanted content detection")
    # Read the transcript from the file
    with open(transcript_file_path, "r") as file:
        transcript = file.read()

    logging.info(f"Transcript length: {len(transcript)} characters")

    if LLM_PROVIDER == "openai":
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = run_with_animation(
            client.chat.completions.create,
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

    elif LLM_PROVIDER == "gemini":
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
            response = run_with_animation(
                model.generate_content,
                prompt
            )

            logging.info("Received response from Gemini")
            json_output = response.text
            logging.info(f"Raw response from Gemini: {json_output}")

            return json_output

        except Exception as e:
            logging.error(f"Error in Gemini processing: {str(e)}")
            raise

    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")



def edit_audio(input_file, output_file, unwanted_content):
    logging.info("Starting audio editing process")
    audio = AudioSegment.from_mp3(input_file)

    # Sort unwanted content by start time
    unwanted_content.sort(key=lambda x: float(x['start_time']))

    # Create a new audio file with unwanted content removed
    edited_audio = AudioSegment.empty()
    last_end = 0
    total_segments = len(unwanted_content)

    def process_segments():
        nonlocal last_end, edited_audio
        for i, segment in enumerate(unwanted_content, 1):
            start = float(segment['start_time']) * 1000  # Convert to milliseconds
            end = float(segment['end_time']) * 1000

            # Add the audio before the unwanted content
            edited_audio += audio[last_end:start]

            # Update the last_end to the end of this unwanted segment
            last_end = end

            logging.info(f"Processed segment {i}/{total_segments}: {segment['description']}")

        # Add any remaining audio after the last unwanted segment
        edited_audio += audio[last_end:]

    # Run the segment processing with animation
    run_with_animation(process_segments)

    logging.info("Exporting edited audio...")
    # Export the edited audio with animation
    run_with_animation(edited_audio.export, output_file, format="mp3")
    logging.info(f"Edited audio saved to {output_file}")

# If the file podcast_uncut.mp3 doesn't yet exist, download the podcast and rename it to podcast_uncut.mp3
if not os.path.exists("input/podcast_uncut.mp3"):
    print("Downloading podcast...")
    podcast_url = PODCAST_URL
    run_with_animation(subprocess.run, ["wget", podcast_url, "-O", "input/podcast_uncut.mp3"])
    print("Downloaded podcast")

# Check if transcript.txt already exists
if not os.path.exists("output/transcript.txt"):
    print("Running Whisper...")

    # Run Whisper to transcribe
    model = whisper.load_model("base")
    result = run_with_animation(model.transcribe, "input/podcast_uncut.mp3")

    print("Whisper complete")

    # Output the transcription to a file that includes timestamps
    with open("output/transcript.txt", "w") as f:
        for i, item in enumerate(result["segments"]):
            f.write(f"{item['start']} - {item['end']}: {item['text']}\n")

    print("Transcription complete")
else:
    print("Transcript file already exists. Skipping Whisper transcription.")

# Check if unwanted_content.json already exists
if not os.path.exists("output/unwanted_content.json"):
    # Send the transcription to the selected LLM to identify timestamps of unwanted content
    logging.info("Sending transcript to LLM for processing")
    unwanted_content = find_unwanted_content("output/transcript.txt")

    logging.info("LLM processing complete")

    # Parse the unwanted_content JSON
    try:
        logging.info("Attempting to parse LLM response as JSON")
        unwanted_content_data = json.loads(unwanted_content)
        if "unwanted_content" in unwanted_content_data:
            unwanted_content_list = unwanted_content_data["unwanted_content"]
            logging.info(f"Successfully parsed JSON. Found {len(unwanted_content_list)} unwanted content sections")
        else:
            raise ValueError("Expected 'unwanted_content' key not found in JSON response")
    except (json.JSONDecodeError, ValueError) as e:
        logging.error(f"Error parsing JSON: {e}")
        logging.error(f"Raw LLM response: {unwanted_content}")
        exit(1)

    # Write the unwanted_content_data to a file
    with open("output/unwanted_content.json", "w") as f:
        json.dump(unwanted_content_data, f, indent=2)
        logging.info("Wrote unwanted content data to output/unwanted_content.json")
else:
    logging.info("unwanted_content.json already exists. Skipping LLM processing.")
    # Load existing unwanted_content data
    with open("output/unwanted_content.json", "r") as f:
        unwanted_content_data = json.load(f)
    logging.info(f"Loaded existing unwanted content data with {len(unwanted_content_data['unwanted_content'])} sections")

# Edit the audio file
input_file = "input/podcast_uncut.mp3"
output_file = "output/podcast_edited.mp3"

logging.info("Starting audio editing process")
edit_audio(input_file, output_file, unwanted_content_data['unwanted_content'])
logging.info("Audio editing completed")

logging.info("Script completed successfully")
