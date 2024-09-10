from audio_editor import edit_audio
from llm_processor import find_unwanted_content, parse_llm_response
from utils import get_podcast_episodes, download_episode, run_with_animation
import whisper
import os
import logging
import json
import time

def process_podcast_episode(rss_url, episode_index=0):
    logging.info(f"Starting to process podcast episode from RSS: {rss_url}")

    # Get available episodes
    logging.info("Fetching available episodes...")
    episodes = run_with_animation(get_podcast_episodes, rss_url)
    logging.info(f"Found {len(episodes)} episodes")

    if episode_index >= len(episodes):
        raise ValueError("Episode index out of range")

    chosen_episode = episodes[episode_index]
    logging.info(f"Selected episode: {chosen_episode['title']}")

    # Create input and output directories if they don't exist
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    logging.info("Ensured input and output directories exist")

    # Download the chosen episode
    input_filename = f"input/{chosen_episode['title'].replace(' ', '_')}.mp3"
    logging.info(f"Downloading episode to {input_filename}")
    run_with_animation(download_episode, chosen_episode['url'], input_filename)
    logging.info("Episode download completed")

    # Run Whisper to transcribe with animation
    logging.info("Initializing Whisper model for transcription...")
    model = whisper.load_model("base")

    def transcribe():
        logging.info("Starting transcription process...")
        start_time = time.time()
        result = model.transcribe(input_filename)
        end_time = time.time()
        logging.info(f"Transcription completed in {end_time - start_time:.2f} seconds")
        return result

    logging.info("Running transcription with animation...")
    result = run_with_animation(transcribe)

    if result is None or "segments" not in result:
        logging.error("Transcription failed or returned unexpected result")
        raise ValueError("Transcription failed")

    # Output the transcription to a file that includes timestamps
    transcript_filename = f"output/{chosen_episode['title'].replace(' ', '_')}_transcript.txt"
    logging.info(f"Writing transcript to {transcript_filename}")
    with open(transcript_filename, "w") as f:
        for item in result["segments"]:
            f.write(f"{item['start']} - {item['end']}: {item['text']}\n")
    logging.info("Transcript file created successfully")

    # Find unwanted content
    logging.info("Starting unwanted content detection...")
    llm_response = run_with_animation(find_unwanted_content, transcript_filename)
    logging.info("Unwanted content detection completed")

    logging.info("Parsing LLM response...")
    unwanted_content = parse_llm_response(llm_response)
    logging.info(f"Found {len(unwanted_content['unwanted_content'])} segments of unwanted content")

    # Write the unwanted_content to a file
    unwanted_content_filename = f"output/{chosen_episode['title'].replace(' ', '_')}_unwanted_content.json"
    logging.info(f"Writing unwanted content to {unwanted_content_filename}")
    with open(unwanted_content_filename, "w") as f:
        json.dump(unwanted_content, f, indent=2)
    logging.info("Unwanted content file created successfully")

    # Edit the audio file
    output_file = f"output/{chosen_episode['title'].replace(' ', '_')}_edited.mp3"
    logging.info(f"Starting audio editing process. Output file: {output_file}")
    run_with_animation(edit_audio, input_filename, output_file, unwanted_content['unwanted_content'])
    logging.info("Audio editing completed")

    result = {
        "edited_url": f"/output/{os.path.basename(output_file)}",
        "transcript_file": transcript_filename,
        "unwanted_content_file": unwanted_content_filename
    }
    logging.info("Podcast processing completed successfully")
    return result
