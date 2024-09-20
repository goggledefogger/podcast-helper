from flask import jsonify, request, Response, send_from_directory, abort, current_app
from celery_app import app as celery_app
from api.app import app, CORS
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes
from rss_modifier import get_or_create_modified_rss, invalidate_rss_cache
from llm_processor import find_unwanted_content
from audio_editor import edit_audio
from job_manager import update_job_status, get_job_status, append_job_log, get_job_logs, get_current_jobs, delete_job
import json
import logging
import queue
import threading
from urllib.parse import unquote
import requests
import traceback
import uuid
from queue import Queue
from datetime import datetime
import os
import time

PROCESSED_PODCASTS_FILE = 'output/processed_podcasts.json'
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
    if os.path.exists(PROCESSED_PODCASTS_FILE):
        with open(PROCESSED_PODCASTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_processed_podcast(podcast_data):
    podcasts = load_processed_podcasts()
    podcasts.append(podcast_data)
    logging.info(f"Saving processed podcast: {podcast_data}")
    with open(PROCESSED_PODCASTS_FILE, 'w') as f:
        json.dump(podcasts, f, indent=2)
    logging.info(f"Saved processed podcast to {PROCESSED_PODCASTS_FILE}")

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

@app.route('/api/output/<path:filename>')
def serve_output_file(filename):
    logging.info(f"Attempting to serve file: {filename}")

    # Decode the filename
    decoded_filename = unquote(filename)

    # Construct the full file path
    file_path = os.path.join(current_app.root_path, '..', 'output', decoded_filename)

    logging.info(f"Full file path: {file_path}")

    # Get the directory and file name
    directory = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)

    if os.path.exists(file_path):
        logging.info(f"File found, serving: {file_path}")
        return send_from_directory(directory, file_name, as_attachment=True)
    else:
        logging.error(f"File not found: {file_path}")
        return jsonify({"error": "File not found"}), 404

@app.route('/api/modified_rss/<path:rss_url>')
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

        host = request.headers.get('Host')
        url_root = f"{request.scheme}://{host}/"
        logging.info(f"URL root: {url_root}")

        modified_rss = get_or_create_modified_rss(decoded_rss_url, processed_podcasts, url_root)

        if not modified_rss:
            logging.error("Failed to generate modified RSS")
            return jsonify({"error": "Failed to generate modified RSS"}), 400

        logging.info("Successfully generated modified RSS")
        logging.info(f"Modified RSS content (first 200 chars): {modified_rss[:200]}")
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

if __name__ == '__main__':
    app.run(debug=True)
