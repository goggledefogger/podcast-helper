from audio_editor import edit_audio
from llm_processor import find_unwanted_content, parse_llm_response
from utils import (
    get_podcast_episodes, download_episode, run_with_animation,
    save_processed_podcast, file_path_to_url, safe_filename,
    get_episode_folder, upload_to_firebase, PROCESSED_PODCASTS_FILE,
    file_exists_in_firebase, download_from_firebase, load_processed_podcasts,
    get_db
)
from job_manager import update_job_status
import whisper
import os
import shutil
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
        episodes = run_with_animation(get_podcast_episodes, rss_url)
        if episode_index >= len(episodes):
            raise ValueError("Episode index out of range")

        chosen_episode = episodes[episode_index]
        podcast_title = episodes[0]['podcast_title']
        episode_title = chosen_episode['title']

        # Set job status in Redis
        db = get_db()
        job_key = f"job:{rss_url}:{episode_title}"
        db.set(job_key, 'in_progress')

        # Create episode folder
        episode_folder = get_episode_folder(podcast_title, chosen_episode['title'])
        os.makedirs(episode_folder, exist_ok=True)
        logging.info(f"Created episode folder: {episode_folder}")

        # Load processed podcasts
        processed_podcasts = load_processed_podcasts()
        logging.info(f"Loaded processed podcasts. Type: {type(processed_podcasts)}")
        logging.info(f"Processed podcasts content: {str(processed_podcasts)[:1000]}...")  # Log the first 1000 characters

        # Check if this episode has been processed before
        existing_podcast = next((p for p in processed_podcasts['processed_podcasts'].get(rss_url, [])
                                 if p.get('episode_title') == chosen_episode['title']), None)

        if existing_podcast:
            logging.info(f"Found existing podcast: {existing_podcast}")
            if existing_podcast.get('status') == 'completed':
                logging.info(f"Episode '{chosen_episode['title']}' has already been fully processed. Skipping.")
                return existing_podcast
            elif existing_podcast.get('transcript_file') and existing_podcast.get('input_file'):
                logging.info(f"Episode '{chosen_episode['title']}' has already been downloaded and transcribed. Skipping to content detection.")
                podcast_data = existing_podcast
            else:
                logging.info(f"Episode '{chosen_episode['title']}' is partially processed. Continuing from last step.")
                podcast_data = existing_podcast
        else:
            logging.info("No existing podcast found. Starting from scratch.")
            podcast_data = {
                "podcast_title": podcast_title,
                "episode_title": chosen_episode['title'],
                "rss_url": rss_url,
                "status": "processing",
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "image_url": episodes[0].get('image_url', '')  # Get the image URL from the first episode
            }

        # Update file paths to use Firebase Storage URLs
        input_filename = safe_filename(f"original_{chosen_episode['title']}.mp3")
        transcript_filename = "transcript.txt"
        unwanted_content_filename = "unwanted_content.json"
        output_file = safe_filename(f"edited_{chosen_episode['title']}.mp3")

        # Download the episode if it hasn't been downloaded yet
        if 'input_file' not in podcast_data:
            # Download the episode if it doesn't exist
            logging.info("STAGE:DOWNLOAD:Starting")
            logging.info(f"Downloading episode to {os.path.join(episode_folder, input_filename)}")
            update_job_status(job_id, 'in_progress', 'DOWNLOAD', 30, 'Downloading episode')
            run_with_animation(download_episode, chosen_episode['url'], os.path.join(episode_folder, input_filename))
            logging.info("STAGE:DOWNLOAD:Completed")
            update_job_status(job_id, 'in_progress', 'DOWNLOAD', 40, 'Episode downloaded')
            podcast_data['status'] = 'downloaded'
            podcast_data['input_file'] = upload_to_firebase(os.path.join(episode_folder, input_filename))
            logging.info(f"Uploaded input file to Firebase: {podcast_data['input_file']}")

        save_processed_podcast(podcast_data)

        # Transcribe the audio if it hasn't been transcribed yet
        if 'transcript_file' not in podcast_data:
            # Transcribe the audio
            logging.info("STAGE:TRANSCRIPTION:Starting")
            try:
                logging.info("Initializing Whisper model...")
                update_job_status(job_id, 'in_progress', 'TRANSCRIPTION', 50, 'Initializing Whisper model')
                model = whisper.load_model("base")
                logging.info("Whisper model initialized successfully")

                def transcribe():
                    logging.info("Transcribing audio...")
                    try:
                        # Download the input file from Firebase if it's not local
                        if not os.path.exists(os.path.join(episode_folder, input_filename)):
                            success = download_from_firebase(podcast_data['input_file'], os.path.join(episode_folder, input_filename))
                            if not success:
                                raise ValueError(f"Failed to download input file from Firebase: {podcast_data['input_file']}")

                        result = model.transcribe(os.path.join(episode_folder, input_filename))
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

                logging.info(f"Writing transcript to {os.path.join(episode_folder, transcript_filename)}")
                with open(os.path.join(episode_folder, transcript_filename), "w") as f:
                    for item in result["segments"]:
                        f.write(f"{item['start']:.2f} - {item['end']:.2f}: {item['text']}\n")
                logging.info("Transcript file created successfully")
                logging.info("STAGE:TRANSCRIPTION:Completed")
                update_job_status(job_id, 'in_progress', 'TRANSCRIPTION', 60, 'Transcription completed')
                podcast_data['status'] = 'transcribed'
                podcast_data['transcript_file'] = upload_to_firebase(os.path.join(episode_folder, transcript_filename))
                logging.info(f"Uploaded transcript file to Firebase: {podcast_data['transcript_file']}")
                save_processed_podcast(podcast_data)
            except Exception as e:
                logging.error(f"Error in Whisper transcription: {str(e)}")
                logging.error(traceback.format_exc())
                logging.info("STAGE:TRANSCRIPTION:Failed")
                update_job_status(job_id, 'in_progress', 'TRANSCRIPTION', 60, f'Transcription failed: {str(e)}')
                raise

        # Always perform content detection
        logging.info("STAGE:CONTENT_DETECTION:Starting unwanted content detection...")
        update_job_status(job_id, 'in_progress', 'CONTENT_DETECTION', 70, 'Starting unwanted content detection')
        start_time = time.time()

        # Download the transcript file from Firebase if it's not local
        if not os.path.exists(os.path.join(episode_folder, transcript_filename)):
            download_from_firebase(podcast_data['transcript_file'], os.path.join(episode_folder, transcript_filename))

        llm_response = run_with_animation(find_unwanted_content, os.path.join(episode_folder, transcript_filename))
        end_time = time.time()
        logging.info(f"Unwanted content detection completed in {end_time - start_time:.2f} seconds")

        logging.info(f"LLM response: {str(llm_response)[:500]}...")  # Log first 500 characters of the response

        logging.info("Parsing LLM response...")
        unwanted_content = llm_response
        logging.info(f"Found {len(unwanted_content['unwanted_content'])} segments of unwanted content")

        logging.info(f"Writing unwanted content to {os.path.join(episode_folder, unwanted_content_filename)}")
        with open(os.path.join(episode_folder, unwanted_content_filename), "w") as f:
            json.dump(unwanted_content, f, indent=2)
        logging.info("Unwanted content file created successfully")
        logging.info("STAGE:CONTENT_DETECTION:Completed")
        update_job_status(job_id, 'in_progress', 'CONTENT_DETECTION', 80, 'Unwanted content detection completed')
        podcast_data['status'] = 'content_detected'
        podcast_data['unwanted_content_file'] = upload_to_firebase(os.path.join(episode_folder, unwanted_content_filename))
        logging.info(f"Uploaded unwanted content file to Firebase: {podcast_data['unwanted_content_file']}")
        save_processed_podcast(podcast_data)

        # Edit the audio file
        logging.info("STAGE:AUDIO_EDITING:Starting audio editing process...")
        update_job_status(job_id, 'in_progress', 'AUDIO_EDITING', 90, 'Starting audio editing')
        try:
            if unwanted_content['unwanted_content']:
                # Download the input file from Firebase if it's not local
                if not os.path.exists(os.path.join(episode_folder, input_filename)):
                    download_from_firebase(podcast_data['input_file'], os.path.join(episode_folder, input_filename))

                run_with_animation(edit_audio, os.path.join(episode_folder, input_filename), os.path.join(episode_folder, output_file), unwanted_content['unwanted_content'])
                logging.info("Audio editing completed")
                podcast_data['output_file'] = upload_to_firebase(os.path.join(episode_folder, output_file))
            else:
                logging.info("No unwanted content found. Skipping audio editing.")
                podcast_data['output_file'] = podcast_data['input_file']
            podcast_data['status'] = 'edited'
            save_processed_podcast(podcast_data)
        except Exception as e:
            logging.error(f"Error during audio editing: {str(e)}")
            podcast_data['output_file'] = podcast_data['input_file']
            logging.info("Using original audio file due to editing error")
            logging.info("STAGE:AUDIO_EDITING:Failed")
            update_job_status(job_id, 'in_progress', 'AUDIO_EDITING', 90, f'Audio editing failed: {str(e)}')

        result = {
            "podcast_title": podcast_title,
            "episode_title": chosen_episode['title'],
            "rss_url": rss_url,
            "status": "completed",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat(),
            "edited_url": podcast_data['output_file'],
            "transcript_file": podcast_data['transcript_file'],
            "unwanted_content_file": podcast_data['unwanted_content_file']
        }

        logging.info(f"Podcast processing completed successfully. Result: {result}")

        # Update and save the final processed podcast data
        podcast_data.update(result)
        save_processed_podcast(podcast_data)

        update_job_status(job_id, 'completed', 'COMPLETION', 100, 'Podcast processing completed')

        # Cleanup local files
        logging.info("STAGE:CLEANUP:Starting cleanup of local files")
        update_job_status(job_id, 'in_progress', 'CLEANUP', 95, 'Cleaning up local files')

        files_to_delete = [
            os.path.join(episode_folder, input_filename),
            os.path.join(episode_folder, transcript_filename),
            os.path.join(episode_folder, unwanted_content_filename),
            os.path.join(episode_folder, output_file)
        ]

        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Deleted local file: {file_path}")

        if os.path.exists(episode_folder) and not os.listdir(episode_folder):
            shutil.rmtree(episode_folder)
            logging.info(f"Removed empty episode folder: {episode_folder}")

        logging.info("STAGE:CLEANUP:Completed cleanup of local files")
        update_job_status(job_id, 'in_progress', 'CLEANUP', 98, 'Local files cleaned up')

        # Update job status when completed
        db.set(job_key, 'completed')

        return result

    except Exception as e:
        logging.error(f"Error in podcast processing: {str(e)}")
        logging.error(traceback.format_exc())
        update_job_status(job_id, 'failed', 'ERROR', 0, f'Error: {str(e)}')
        # Update job status when failed
        db.set(job_key, 'failed')
        raise
