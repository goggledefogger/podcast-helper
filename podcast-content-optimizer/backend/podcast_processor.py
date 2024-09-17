from audio_editor import edit_audio
from llm_processor import find_unwanted_content, parse_llm_response
from utils import get_podcast_episodes, download_episode, run_with_animation
import whisper
import os
import logging
import json
import time
import torch
import traceback

def get_episode_folder(podcast_title, episode_title):
    safe_podcast_title = "".join([c for c in podcast_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_episode_title = "".join([c for c in episode_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    return os.path.join('output', safe_podcast_title, safe_episode_title)

def process_podcast_episode(rss_url, episode_index=0):
    logging.info(f"Starting to process podcast episode from RSS: {rss_url}")

    try:
        # Get available episodes
        logging.info("STAGE:FETCH_EPISODES:Starting")
        episodes = run_with_animation(get_podcast_episodes, rss_url)
        logging.info(f"Found {len(episodes)} episodes")
        logging.info("STAGE:FETCH_EPISODES:Completed")

        if episode_index >= len(episodes):
            raise ValueError("Episode index out of range")

        chosen_episode = episodes[episode_index]
        podcast_title = episodes[0]['podcast_title']
        logging.info(f"Selected episode: {chosen_episode['title']} from podcast: {podcast_title}")

        # Create episode folder
        episode_folder = get_episode_folder(podcast_title, chosen_episode['title'])
        os.makedirs(episode_folder, exist_ok=True)
        logging.info(f"Created episode folder: {episode_folder}")

        # Update file paths
        input_filename = os.path.join(episode_folder, f"original_{chosen_episode['title'].replace(' ', '_')}.mp3")
        transcript_filename = os.path.join(episode_folder, f"transcript.txt")
        unwanted_content_filename = os.path.join(episode_folder, f"unwanted_content.json")
        output_file = os.path.join(episode_folder, f"edited_{chosen_episode['title'].replace(' ', '_')}.mp3")

        # Download the episode if it doesn't exist
        if not os.path.exists(input_filename):
            logging.info("STAGE:DOWNLOAD:Starting")
            logging.info(f"Downloading episode to {input_filename}")
            run_with_animation(download_episode, chosen_episode['url'], input_filename)
            logging.info("STAGE:DOWNLOAD:Completed")
        else:
            logging.info(f"Using existing audio file: {input_filename}")

        # Check if the file was actually downloaded
        if not os.path.exists(input_filename):
            raise FileNotFoundError(f"Downloaded file not found: {input_filename}")

        logging.info(f"File size of downloaded episode: {os.path.getsize(input_filename)} bytes")

        # Transcribe the audio if transcript doesn't exist
        if not os.path.exists(transcript_filename):
            logging.info("STAGE:TRANSCRIPTION:Starting")
            try:
                logging.info("Initializing Whisper model...")
                model = whisper.load_model("base")
                logging.info("Whisper model initialized successfully")

                def transcribe():
                    logging.info("Transcribing audio...")
                    try:
                        result = model.transcribe(input_filename)
                        logging.info("Transcription completed successfully")
                        return result
                    except Exception as e:
                        logging.error(f"Error during transcription: {str(e)}")
                        logging.error(traceback.format_exc())
                        return None

                logging.info("Starting transcription process...")
                result = run_with_animation(transcribe)
                logging.info("Transcription process finished")

                if result is None or "segments" not in result:
                    raise ValueError("Transcription failed or returned unexpected result")

                logging.info(f"Writing transcript to {transcript_filename}")
                with open(transcript_filename, "w") as f:
                    for item in result["segments"]:
                        f.write(f"{item['start']:.2f} - {item['end']:.2f}: {item['text']}\n")
                logging.info("Transcript file created successfully")
                logging.info("STAGE:TRANSCRIPTION:Completed")
            except Exception as e:
                logging.error(f"Error in Whisper transcription: {str(e)}")
                logging.error(traceback.format_exc())
                logging.info("STAGE:TRANSCRIPTION:Failed")
                raise
        else:
            logging.info(f"Using existing transcript file: {transcript_filename}")

        # Find unwanted content if it doesn't exist
        if not os.path.exists(unwanted_content_filename):
            logging.info("STAGE:CONTENT_DETECTION:Starting unwanted content detection...")
            llm_response = run_with_animation(find_unwanted_content, transcript_filename)
            logging.info("Unwanted content detection completed")

            logging.info("Parsing Gemini response...")
            unwanted_content = parse_llm_response(llm_response)
            logging.info(f"Found {len(unwanted_content['unwanted_content'])} segments of unwanted content")

            logging.info(f"Writing unwanted content to {unwanted_content_filename}")
            with open(unwanted_content_filename, "w") as f:
                json.dump(unwanted_content, f, indent=2)
            logging.info("Unwanted content file created successfully")
            logging.info("STAGE:CONTENT_DETECTION:Completed")
        else:
            logging.info(f"Using existing unwanted content file: {unwanted_content_filename}")
            with open(unwanted_content_filename, "r") as f:
                unwanted_content = json.load(f)

        # Edit the audio file
        logging.info("STAGE:AUDIO_EDITING:Starting audio editing process...")
        try:
            if unwanted_content['unwanted_content']:
                run_with_animation(edit_audio, input_filename, output_file, unwanted_content['unwanted_content'])
                logging.info("Audio editing completed")
            else:
                logging.info("No unwanted content found. Skipping audio editing.")
                output_file = input_filename
        except Exception as e:
            logging.error(f"Error during audio editing: {str(e)}")
            output_file = input_filename
            logging.info("Using original audio file due to editing error")
            logging.info("STAGE:AUDIO_EDITING:Failed")

        result = {
            "podcast_title": podcast_title,
            "episode_title": chosen_episode['title'],
            "edited_url": f"/output/{podcast_title}/{chosen_episode['title']}/{os.path.basename(output_file)}",
            "transcript_file": f"/output/{podcast_title}/{chosen_episode['title']}/{os.path.basename(transcript_filename)}",
            "unwanted_content_file": f"/output/{podcast_title}/{chosen_episode['title']}/{os.path.basename(unwanted_content_filename)}"
        }
        logging.info(f"Podcast processing completed successfully. Result: {result}")
        return result

    except Exception as e:
        logging.error(f"Error in process_podcast_episode: {str(e)}")
        logging.error(traceback.format_exc())
        raise
