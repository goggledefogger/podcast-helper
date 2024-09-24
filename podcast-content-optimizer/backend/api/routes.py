from flask import jsonify, request, Response, send_from_directory, abort, current_app, send_file, redirect
from celery_app import app as celery_app
from api.app import app, CORS
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes, url_to_file_path, file_path_to_url
from rss_modifier import get_or_create_modified_rss, invalidate_rss_cache
from llm_processor import find_unwanted_content
from audio_editor import edit_audio
from job_manager import update_job_status, get_job_status, append_job_log, get_job_logs, get_current_jobs, delete_job
import json
import logging
import queue
import threading
from urllib.parse import unquote, quote
import requests
import traceback
import uuid
from queue import Queue
from datetime import datetime
import os
import time
import shutil
from utils import get_episode_folder
from firebase_admin import storage

# Update the OUTPUT_DIR definition
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))

# Update this line to use the root of the bucket
PROCESSED_PODCASTS_FILE = 'processed_podcasts.json'

log_queue = queue.Queue()

# Add Taddy API configuration
TADDY_API_URL = os.getenv("TADDY_API_URL", "https://api.taddy.org")
TADDY_API_KEY = os.getenv("TADDY_API_KEY")
TADDY_USER_ID = os.getenv("TADDY_USER_ID")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

# Initialize the processing_status dictionary
processing_status = {}

def load_processed_podcasts():
    try:
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        logging.info(f"Attempting to load processed podcasts from Firebase: {PROCESSED_PODCASTS_FILE}")
        if blob.exists():
            json_data = blob.download_as_text()
            podcasts = json.loads(json_data)
            logging.info(f"Successfully loaded {len(podcasts)} processed podcasts from Firebase")
            return podcasts
        else:
            logging.info(f"No processed podcasts file found in Firebase: {PROCESSED_PODCASTS_FILE}")
    except Exception as e:
        logging.error(f"Error loading processed podcasts from Firebase: {str(e)}")
    return []

def save_processed_podcast(podcast_data):
    try:
        # Load existing data or create an empty list
        podcasts = load_processed_podcasts()

        # Check if the podcast already exists in the list
        existing_podcast = next((p for p in podcasts if p['rss_url'] == podcast_data['rss_url'] and p['episode_title'] == podcast_data['episode_title']), None)

        if existing_podcast:
            # Update the existing podcast data
            existing_podcast.update(podcast_data)
            logging.info(f"Updated existing podcast: {podcast_data['episode_title']}")
        else:
            # Append new data
            podcasts.append(podcast_data)
            logging.info(f"Added new podcast: {podcast_data['episode_title']}")

        # Convert file paths to Firebase Storage URLs
        for key in ['edited_url', 'transcript_file', 'unwanted_content_file', 'input_file', 'output_file']:
            if key in podcast_data and podcast_data[key]:
                old_value = podcast_data[key]
                podcast_data[key] = upload_to_firebase(podcast_data[key])
                logging.info(f"Uploaded {key} to Firebase: {old_value} -> {podcast_data[key]}")

        logging.info(f"Saving processed podcast to Firebase: {podcast_data['episode_title']}")

        # Write updated data to Firebase Storage
        json_data = json.dumps(podcasts, indent=2)
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        blob.upload_from_string(json_data, content_type='application/json')

        logging.info(f"Successfully saved processed podcast to Firebase: {PROCESSED_PODCASTS_FILE}")

    except Exception as e:
        logging.error(f"Error saving processed podcast to Firebase: {str(e)}")
        logging.error(traceback.format_exc())

def upload_to_firebase(file_path):
    try:
        blob = storage.bucket().blob(file_path)
        logging.info(f"Uploading file to Firebase: {file_path}")
        blob.upload_from_filename(file_path)
        public_url = blob.public_url
        logging.info(f"Successfully uploaded file to Firebase: {file_path} -> {public_url}")
        return public_url
    except Exception as e:
        logging.error(f"Error uploading file to Firebase: {file_path}, Error: {str(e)}")
        return None

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/episodes', methods=['POST'])
def get_episodes():
    try:
        data = request.json
        logging.info(f"Received request data for /api/episodes: {data}")

        rss_url = data.get('rss_url')
        if not rss_url:
            logging.error("No RSS URL provided in the request")
            return jsonify({"error": "No RSS URL provided"}), 400

        logging.info(f"Fetching episodes for RSS URL: {rss_url}")
        episodes = get_podcast_episodes(rss_url)
        logging.info(f"Successfully fetched {len(episodes)} episodes")
        return jsonify(episodes), 200
    except ValueError as ve:
        logging.error(f"ValueError in get_episodes: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in get_episodes: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/processed_podcasts', methods=['GET'])
def get_processed_podcasts():
    processed_podcasts = load_processed_podcasts()
    logging.info(f"Fetched {len(processed_podcasts)} processed podcasts")
    return jsonify(processed_podcasts), 200

@app.route('/output/<path:filename>')
def serve_output_file(filename):
    logging.info(f"Attempting to serve file from Firebase Storage: {filename}")

    try:
        blob = storage.bucket().blob(filename)
        if blob.exists():
            public_url = blob.public_url
            logging.info(f"File found in Firebase Storage, redirecting to: {public_url}")
            return redirect(public_url)
        else:
            logging.error(f"File not found in Firebase Storage: {filename}")
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        logging.error(f"Error serving file from Firebase Storage: {filename}, Error: {str(e)}")
        return jsonify({"error": f"Error serving file: {str(e)}"}), 500

@app.route('/api/modified_rss/<path:rss_url>', methods=['GET'])
def get_modified_rss(rss_url):
    try:
        logging.info(f"Attempting to get modified RSS for URL: {rss_url}")

        # Decode the URL twice to handle double encoding
        decoded_rss_url = unquote(unquote(rss_url))
        logging.info(f"Decoded RSS URL: {decoded_rss_url}")

        # Check if the decoded URL starts with 'http://' or 'https://'
        if not decoded_rss_url.startswith(('http://', 'https://')):
            # If not, assume it's missing the scheme and prepend 'https://'
            decoded_rss_url = 'https://' + decoded_rss_url
            logging.info(f"Added https:// to URL: {decoded_rss_url}")

        processed_podcasts = load_processed_podcasts()
        logging.info(f"Loaded {len(processed_podcasts)} processed podcasts")

        modified_rss = get_or_create_modified_rss(decoded_rss_url, processed_podcasts)

        if not modified_rss:
            logging.error("Failed to generate modified RSS")
            return jsonify({"error": "Failed to generate modified RSS"}), 400

        logging.info("Successfully generated modified RSS")
        return Response(modified_rss, content_type='application/xml; charset=utf-8')
    except Exception as e:
        logging.error(f"Error generating modified RSS: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 400

from api.tasks import process_podcast_task  # Import the task directly

@app.route('/api/process', methods=['POST'])
def process_episode():
    rss_url = request.json.get('rss_url')
    episode_index = request.json.get('episode_index')

    if not rss_url or episode_index is None:
        return jsonify({"error": "Missing RSS URL or episode index"}), 400

    job_id = str(uuid.uuid4())
    update_job_status(job_id, 'queued', 'INITIALIZATION', 0, 'Job queued')
    append_job_log(job_id, {'stage': 'INITIALIZATION', 'message': 'Job queued'})

    # Add the podcast to processed_podcasts.json with 'processing' status
    episodes = get_podcast_episodes(rss_url)
    if episode_index < len(episodes):
        episode = episodes[episode_index]
        podcast_data = {
            "podcast_title": episode['podcast_title'],
            "episode_title": episode['title'],
            "rss_url": rss_url,
            "status": "processing",
            "job_id": job_id,
            "timestamp": datetime.now().isoformat()
        }
        save_processed_podcast(podcast_data)

    logging.info(f"Queueing task for job_id: {job_id}")
    task = process_podcast_task.delay(rss_url, episode_index, job_id)
    logging.info(f"Task queued with task_id: {task.id} for job_id: {job_id}")

    return jsonify({"message": "Processing started", "job_id": job_id}), 202

@app.route('/api/process_status/<job_id>', methods=['GET'])
def get_process_status(job_id):
    status = get_job_status(job_id)
    logs = get_job_logs(job_id)
    if status:
        return jsonify({"status": status, "logs": logs})
    else:
        return jsonify({"error": "Job not found"}), 404

@app.route('/api/search', methods=['POST'])
def search():
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "No search query provided"}), 400

    podcasts = search_podcasts(query)
    return jsonify(podcasts), 200

def search_podcasts(query):
    headers = {
        "Content-Type": "application/json",
        "X-USER-ID": TADDY_USER_ID,
        "X-API-KEY": TADDY_API_KEY
    }

    graphql_query = {
        "query": f"""
        query {{
          getPodcastSeries(name: "{query}") {{
            uuid
            name
            description
            imageUrl
            rssUrl
          }}
        }}
        """
    }

    response = requests.post(TADDY_API_URL, json=graphql_query, headers=headers)

    if response.status_code == 200:
        data = response.json()
        podcasts_data = data.get("data", {}).get("getPodcastSeries")

        if podcasts_data is None:
            logging.warning(f"No podcasts found for query: {query}")
            return []

        if isinstance(podcasts_data, dict):
            podcasts = [podcasts_data]
        elif isinstance(podcasts_data, list):
            podcasts = podcasts_data
        else:
            logging.error(f"Unexpected data type for podcasts: {type(podcasts_data)}")
            return []

        return podcasts
    else:
        logging.error(f"Error searching podcasts: {response.text}")
        return []

@app.route('/api/current_jobs', methods=['GET'])
def get_current_jobs_route():
    jobs = get_current_jobs()
    return jsonify(jobs), 200

@app.route('/api/delete_job/<job_id>', methods=['DELETE', 'OPTIONS'])
def delete_job_route(job_id):
    if request.method == 'OPTIONS':
        return '', 204
    try:
        delete_job(job_id)
        return jsonify({"message": f"Job {job_id} deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting job {job_id}: {str(e)}")
        return jsonify({"error": f"Failed to delete job: {str(e)}"}), 500

@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 204

@app.route('/api/batch_process_status', methods=['POST'])
def batch_process_status():
    try:
        data = request.json
        job_ids = data.get('job_ids', [])

        if not job_ids:
            return jsonify({"error": "No job IDs provided"}), 400

        statuses = {}
        for job_id in job_ids:
            status = get_job_status(job_id)
            if status:
                statuses[job_id] = status

        return jsonify(statuses), 200
    except Exception as e:
        logging.error(f"Error in batch_process_status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete_processed_podcast', methods=['POST'])
def delete_processed_podcast():
    try:
        data = request.json
        podcast_title = data.get('podcast_title')
        episode_title = data.get('episode_title')

        if not podcast_title or not episode_title:
            return jsonify({"error": "Missing podcast title or episode title"}), 400

        # Load existing processed podcasts
        processed_podcasts = load_processed_podcasts()

        # Find and remove the podcast from the list
        processed_podcasts = [p for p in processed_podcasts if not (p['podcast_title'] == podcast_title and p['episode_title'] == episode_title)]

        # Save the updated list
        json_data = json.dumps(processed_podcasts, indent=2)
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        blob.upload_from_string(json_data, content_type='application/json')

        # Delete files from Firebase Storage
        episode_folder = get_episode_folder(podcast_title, episode_title)
        for root, dirs, files in os.walk(episode_folder):
            for file in files:
                file_path = os.path.join(root, file)
                blob = storage.bucket().blob(file_path)
                if blob.exists():
                    blob.delete()
                    logging.info(f"Deleted file from Firebase Storage: {file_path}")

        # Invalidate the RSS cache for this podcast
        invalidate_rss_cache(data.get('rss_url'))

        return jsonify({"message": "Podcast deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting processed podcast: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# Update the CORS configuration to allow DELETE method
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS", "DELETE"]}})

if __name__ == '__main__':
    app.run(debug=True)
