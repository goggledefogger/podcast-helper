from flask import jsonify, request, Response
from api.app import app
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes
from rss_modifier import get_or_create_modified_rss, invalidate_rss_cache
import json
import os
import logging
import queue
import threading
from urllib.parse import unquote
import requests
import traceback
import uuid
from queue import Queue
from datetime import datetime  # Add this import

PROCESSED_PODCASTS_FILE = 'output/processed_podcasts.json'
log_queue = queue.Queue()

# Add Taddy API configuration
TADDY_API_URL = os.getenv("TADDY_API_URL", "https://api.taddy.org")
TADDY_API_KEY = os.getenv("TADDY_API_KEY")
TADDY_USER_ID = os.getenv("TADDY_USER_ID")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

class QueueHandler(logging.Handler):
    def __init__(self, job_id=None):
        super().__init__()
        self.job_id = job_id

    def emit(self, record):
        log_entry = self.format(record)
        if self.job_id:
            processing_status[self.job_id]['logs'].append(log_entry)
            if "STAGE:" in log_entry:
                stage = log_entry.split("STAGE:")[1].split(":")[0]
                processing_status[self.job_id]['current_stage'] = stage
        else:
            # Handle global logging (not associated with a specific job)
            print(log_entry)  # or use another method to store/display logs

# Initialize a global QueueHandler without a job_id
queue_handler = QueueHandler()
logger.addHandler(queue_handler)

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
    with open(PROCESSED_PODCASTS_FILE, 'w') as f:
        json.dump(podcasts, f, indent=2)

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

@app.route('/api/process', methods=['POST'])
def process_episode():
    rss_url = request.json.get('rss_url')
    episode_index = request.json.get('episode_index')

    if not rss_url or episode_index is None:
        return jsonify({"error": "Missing RSS URL or episode index"}), 400

    job_id = str(uuid.uuid4())  # Generate a unique job ID

    processing_status[job_id] = {
        'status': 'queued',
        'progress': 0,
        'logs': [],
        'current_stage': 'Queued',
        'start_time': None,
        'end_time': None
    }

    def process():
        try:
            # Create a job-specific QueueHandler
            job_queue_handler = QueueHandler(job_id)

            # Redirect all logs to the job-specific handler
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            logging.root.addHandler(job_queue_handler)

            processing_status[job_id]['status'] = 'in_progress'
            processing_status[job_id]['start_time'] = datetime.now().isoformat()

            result = process_podcast_episode(rss_url, episode_index)

            if isinstance(result, dict) and "error" in result:
                processing_status[job_id]['status'] = 'failed'
                processing_status[job_id]['logs'].append(f"Error: {result['error']}")
            else:
                save_processed_podcast(result)
                processing_status[job_id]['status'] = 'completed'
                processing_status[job_id]['logs'].append("Podcast processing completed successfully")

        except Exception as e:
            processing_status[job_id]['status'] = 'failed'
            processing_status[job_id]['logs'].append(f"Error: {str(e)}")
        finally:
            processing_status[job_id]['current_stage'] = 'Finished'
            processing_status[job_id]['end_time'] = datetime.now().isoformat()
            # Restore the global logger configuration
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            logging.root.addHandler(queue_handler)

    threading.Thread(target=process).start()
    return jsonify({"message": "Processing started", "job_id": job_id}), 202

@app.route('/api/stream')
def stream():
    def generate():
        while True:
            try:
                log_entry = log_queue.get(timeout=1)
                if log_entry:
                    yield f"data: {log_entry}\n\n"
            except queue.Empty:
                yield "data: \n\n"  # Send an empty message to keep the connection alive

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/processed_podcasts', methods=['GET'])
def get_processed_podcasts():
    processed_podcasts = load_processed_podcasts()
    return jsonify(processed_podcasts), 200

@app.route('/api/modified_rss/<path:rss_url>')
def get_modified_rss(rss_url):
    try:
        decoded_rss_url = unquote(rss_url)
        processed_podcasts = load_processed_podcasts()
        host = request.headers.get('Host')
        url_root = f"{request.scheme}://{host}/"
        modified_rss = get_or_create_modified_rss(decoded_rss_url, processed_podcasts, url_root)
        return modified_rss, 200, {'Content-Type': 'application/xml; charset=utf-8'}
    except Exception as e:
        logging.error(f"Error generating modified RSS: {str(e)}")
        return jsonify({"error": str(e)}), 400

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

@app.route('/api/process_status/<job_id>', methods=['GET'])
def get_process_status(job_id):
    if job_id in processing_status:
        return jsonify(processing_status[job_id])
    else:
        return jsonify({"error": "Job not found"}), 404

# Remove the /api/search route as we've removed the search_podcasts function
