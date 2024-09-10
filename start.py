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
import feedparser
import requests
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

logging.info(f"Using LLM provider: {LLM_PROVIDER}")

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

def get_podcast_episodes(rss_url):
    feed = feedparser.parse(rss_url)
    episodes = []
    for entry in feed.entries:
        for link in entry.links:
            if link.type == 'audio/mpeg':
                episodes.append({
                    'title': entry.title,
                    'url': link.href,
                    'published': entry.published
                })
                break
    return episodes

def choose_episode(episodes):
    total_episodes = len(episodes)
    current_page = 0
    episodes_per_page = 10

    while True:
        start_index = current_page * episodes_per_page
        end_index = min(start_index + episodes_per_page, total_episodes)

        print(f"\nShowing episodes {start_index + 1} to {end_index} of {total_episodes}:")
        for i, episode in enumerate(episodes[start_index:end_index], start_index + 1):
            print(f"{i}. {episode['title']} - {episode['published']}")

        print("\nOptions:")
        print("Enter a number to select an episode")
        if current_page > 0:
            print("P: Previous page")
        if end_index < total_episodes:
            print("N: Next page")
        print("Q: Quit")

        choice = input("Enter your choice: ").strip().lower()

        if choice == 'q':
            print("Exiting...")
            sys.exit(0)
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'n' and end_index < total_episodes:
            current_page += 1
        elif choice.isdigit():
            episode_num = int(choice)
            if 1 <= episode_num <= total_episodes:
                return episodes[episode_num - 1]
            else:
                print("Invalid episode number. Please try again.")
        else:
            print("Invalid input. Please try again.")

def download_episode(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 KB

    with open(filename, 'wb') as file, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(block_size):
            size = file.write(data)
            progress_bar.update(size)

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Get podcast RSS feed URL from user
    rss_url = input("Enter the podcast RSS feed URL: ")

    # Get available episodes
    episodes = get_podcast_episodes(rss_url)

    # Let user choose an episode
    chosen_episode = choose_episode(episodes)

    # Create input and output directories if they don't exist
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # Download the chosen episode
    input_filename = f"input/{chosen_episode['title'].replace(' ', '_')}.mp3"
    print(f"Downloading episode: {chosen_episode['title']}")
    download_episode(chosen_episode['url'], input_filename)
    print("Download complete")

    # Run Whisper to transcribe
    print("Running Whisper...")
    model = whisper.load_model("base")
    result = run_with_animation(model.transcribe, input_filename)
    print("Whisper complete")

    # Output the transcription to a file that includes timestamps
    transcript_filename = f"output/{chosen_episode['title'].replace(' ', '_')}_transcript.txt"
    with open(transcript_filename, "w") as f:
        for i, item in enumerate(result["segments"]):
            f.write(f"{item['start']} - {item['end']}: {item['text']}\n")
    print("Transcription complete")

    # Send the transcription to the selected LLM to identify timestamps of unwanted content
    logging.info("Sending transcript to LLM for processing")
    unwanted_content = find_unwanted_content(transcript_filename)

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
    unwanted_content_filename = f"output/{chosen_episode['title'].replace(' ', '_')}_unwanted_content.json"
    with open(unwanted_content_filename, "w") as f:
        json.dump(unwanted_content_data, f, indent=2)
        logging.info(f"Wrote unwanted content data to {unwanted_content_filename}")

    # Edit the audio file
    output_file = f"output/{chosen_episode['title'].replace(' ', '_')}_edited.mp3"

    logging.info("Starting audio editing process")
    edit_audio(input_filename, output_file, unwanted_content_data['unwanted_content'])
    logging.info("Audio editing completed")

    logging.info("Script completed successfully")
