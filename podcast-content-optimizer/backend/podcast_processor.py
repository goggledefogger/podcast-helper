from audio_editor import edit_audio
from llm_processor import find_unwanted_content, parse_llm_response
from utils import get_podcast_episodes, download_episode, run_with_animation, save_processed_podcast, file_path_to_url, safe_filename, get_episode_folder, file_path_to_url
from job_manager import update_job_status
import whisper
import os
import logging
import json
import time
import torch
import traceback
import urllib.parse
from datetime import datetime

def process_podcast_episode(rss_url, episode_index=0, job_id=None):
    logging.info(f"Starting to process podcast episode from RSS: {rss_url}")

    try:
        # Get available episodes
        logging.info("STAGE:FETCH_EPISODES:Starting")
        update_job_status(job_id, 'in_progress', 'FETCH_EPISODES', 10, 'Fetching episodes')
        episodes = run_with_animation(get_podcast_episodes, rss_url)
        logging.info(f"Found {len(episodes)} episodes")
        logging.info("STAGE:FETCH_EPISODES:Completed")
        update_job_status(job_id, 'in_progress', 'FETCH_EPISODES', 20, 'Episodes fetched')

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
        input_filename = os.path.join(episode_folder, safe_filename(f"original_{chosen_episode['title']}.mp3"))
        transcript_filename = os.path.join(episode_folder, "transcript.txt")
        unwanted_content_filename = os.path.join(episode_folder, "unwanted_content.json")
        output_file = os.path.join(episode_folder, safe_filename(f"edited_{chosen_episode['title']}.mp3"))

        # Create initial podcast data
        podcast_data = {
            "podcast_title": podcast_title,
            "episode_title": chosen_episode['title'],
            "rss_url": rss_url,
            "status": "processing",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat()
        }
        save_processed_podcast(podcast_data)

        # Download the episode if it doesn't exist
        if not os.path.exists(input_filename):
            logging.info("STAGE:DOWNLOAD:Starting")
            logging.info(f"Downloading episode to {input_filename}")
            update_job_status(job_id, 'in_progress', 'DOWNLOAD', 30, 'Downloading episode')
            run_with_animation(download_episode, chosen_episode['url'], input_filename)
            logging.info("STAGE:DOWNLOAD:Completed")
            update_job_status(job_id, 'in_progress', 'DOWNLOAD', 40, 'Episode downloaded')
            podcast_data['status'] = 'downloaded'
            podcast_data['input_file'] = input_filename
            save_processed_podcast(podcast_data)
        else:
            logging.info(f"Using existing audio file: {input_filename}")
            podcast_data['input_file'] = input_filename
            save_processed_podcast(podcast_data)

        if not os.path.exists(input_filename):
            raise FileNotFoundError(f"Downloaded file not found: {input_filename}")

        logging.info(f"File size of downloaded episode: {os.path.getsize(input_filename)} bytes")

        # Transcribe the audio if transcript doesn't exist
        if not os.path.exists(transcript_filename):
            logging.info("STAGE:TRANSCRIPTION:Starting")
            try:
                logging.info("Initializing Whisper model...")
                update_job_status(job_id, 'in_progress', 'TRANSCRIPTION', 50, 'Initializing Whisper model')
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
                update_job_status(job_id, 'in_progress', 'TRANSCRIPTION', 60, 'Transcription completed')
                podcast_data['status'] = 'transcribed'
                podcast_data['transcript_file'] = transcript_filename
                save_processed_podcast(podcast_data)
            except Exception as e:
                logging.error(f"Error in Whisper transcription: {str(e)}")
                logging.error(traceback.format_exc())
                logging.info("STAGE:TRANSCRIPTION:Failed")
                update_job_status(job_id, 'in_progress', 'TRANSCRIPTION', 60, f'Transcription failed: {str(e)}')
                raise
        else:
            logging.info(f"Using existing transcript file: {transcript_filename}")
            podcast_data['transcript_file'] = transcript_filename
            save_processed_podcast(podcast_data)

        # Always perform content detection
        logging.info("STAGE:CONTENT_DETECTION:Starting unwanted content detection...")
        update_job_status(job_id, 'in_progress', 'CONTENT_DETECTION', 70, 'Starting unwanted content detection')
        start_time = time.time()
        llm_response = run_with_animation(find_unwanted_content, transcript_filename)
        end_time = time.time()
        logging.info(f"Unwanted content detection completed in {end_time - start_time:.2f} seconds")

        logging.info(f"LLM response: {str(llm_response)[:500]}...")  # Log first 500 characters of the response

        logging.info("Parsing LLM response...")
        unwanted_content = llm_response
        logging.info(f"Found {len(unwanted_content['unwanted_content'])} segments of unwanted content")

        logging.info(f"Writing unwanted content to {unwanted_content_filename}")
        with open(unwanted_content_filename, "w") as f:
            json.dump(unwanted_content, f, indent=2)
        logging.info("Unwanted content file created successfully")
        logging.info("STAGE:CONTENT_DETECTION:Completed")
        update_job_status(job_id, 'in_progress', 'CONTENT_DETECTION', 80, 'Unwanted content detection completed')
        podcast_data['status'] = 'content_detected'
        podcast_data['unwanted_content_file'] = unwanted_content_filename
        save_processed_podcast(podcast_data)

        # Edit the audio file
        logging.info("STAGE:AUDIO_EDITING:Starting audio editing process...")
        update_job_status(job_id, 'in_progress', 'AUDIO_EDITING', 90, 'Starting audio editing')
        try:
            if unwanted_content['unwanted_content']:
                run_with_animation(edit_audio, input_filename, output_file, unwanted_content['unwanted_content'])
                logging.info("Audio editing completed")
                podcast_data['output_file'] = output_file
            else:
                logging.info("No unwanted content found. Skipping audio editing.")
                podcast_data['output_file'] = input_filename
            podcast_data['status'] = 'edited'
            save_processed_podcast(podcast_data)
        except Exception as e:
            logging.error(f"Error during audio editing: {str(e)}")
            output_file = input_filename
            podcast_data['output_file'] = input_filename
            logging.info("Using original audio file due to editing error")
            logging.info("STAGE:AUDIO_EDITING:Failed")
            update_job_status(job_id, 'in_progress', 'AUDIO_EDITING', 90, f'Audio editing failed: {str(e)}')

        result = {
            "podcast_title": podcast_title,
            "episode_title": chosen_episode['title'],
            "rss_url": rss_url,
            "status": "completed",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat()
        }

        # Add file references only if they exist
        if os.path.exists(output_file):
            result["edited_url"] = file_path_to_url(output_file)
        if os.path.exists(transcript_filename):
            result["transcript_file"] = file_path_to_url(transcript_filename)
        if os.path.exists(unwanted_content_filename):
            result["unwanted_content_file"] = file_path_to_url(unwanted_content_filename)

        logging.info(f"Podcast processing completed successfully. Result: {result}")

        # Update and save the final processed podcast data
        podcast_data.update(result)
        save_processed_podcast(podcast_data)

        update_job_status(job_id, 'completed', 'COMPLETION', 100, 'Podcast processing completed')
        return result

    except Exception as e:
        logging.error(f"Error in podcast processing: {str(e)}")
        logging.error(traceback.format_exc())
        update_job_status(job_id, 'failed', 'ERROR', 0, f'Error: {str(e)}')
        raise
