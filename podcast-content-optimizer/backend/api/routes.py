from flask import jsonify, request, Response, send_from_directory, abort, current_app, send_file, redirect, render_template_string, url_for, render_template, make_response
from celery_app import app as celery_app
from api.app import app, CORS
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes, url_to_file_path, file_path_to_url, load_auto_processed_podcasts, save_auto_processed_podcasts, is_episode_processed, load_processed_podcasts, get_db, save_processed_podcasts
from rss_modifier import create_modified_rss_feed, get_modified_rss_feed
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
from prompt_loader import load_prompt
import feedparser
from api.tasks import process_podcast_task
from datetime import datetime, timedelta
import pytz
from utils import save_auto_processed_podcast, load_processed_podcasts
from rss_modifier import get_modified_rss_feed

# Update the OUTPUT_DIR definition
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))

# Update this line to use the root of the bucket
PROCESSED_PODCASTS_FILE = 'db.json'

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

# Update the template folder path
template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
app.template_folder = template_dir

def load_processed_podcasts():
    try:
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        if blob.exists():
            json_data = blob.download_as_text()
            data = json.loads(json_data)
            return {
                'processed_podcasts': data.get('processed_podcasts', {}),
                'auto_processed_podcasts': data.get('auto_processed_podcasts', []),
                'podcast_info': data.get('podcast_info', {}),  # Change this to {}
                'prompts': data.get('prompts', {})
            }
        else:
            return {'processed_podcasts': {}, 'auto_processed_podcasts': [], 'podcast_info': {}, 'prompts': {}}
    except Exception as e:
        logging.error(f"Error loading processed podcasts from Firebase: {str(e)}")
        logging.error(traceback.format_exc())
        return {'processed_podcasts': {}, 'auto_processed_podcasts': [], 'podcast_info': {}, 'prompts': {}}

def save_processed_podcast(podcast_data):
    try:
        # Load existing data
        data = load_processed_podcasts()
        rss_url = podcast_data['rss_url']

        if rss_url not in data['processed_podcasts']:
            data['processed_podcasts'][rss_url] = []

        # Check if the episode already exists
        existing_episode = next((ep for ep in data['processed_podcasts'][rss_url] if ep['episode_title'] == podcast_data['episode_title']), None)

        if existing_episode:
            # Update the existing episode data
            existing_episode.update(podcast_data)
            logging.info(f"Updated existing episode: {podcast_data['episode_title']}")
        else:
            # Append new episode data
            data['processed_podcasts'][rss_url].append(podcast_data)
            logging.info(f"Added new episode: {podcast_data['episode_title']}")

        # Convert file paths to Firebase Storage URLs
        for key in ['edited_url', 'transcript_file', 'unwanted_content_file', 'input_file', 'output_file']:
            if key in podcast_data and podcast_data[key]:
                old_value = podcast_data[key]
                podcast_data[key] = upload_to_firebase(podcast_data[key])
                logging.info(f"Uploaded {key} to Firebase: {old_value} -> {podcast_data[key]}")

        # Update podcast info
        data['podcast_info'][rss_url] = {
            'name': podcast_data['podcast_title'],
            'imageUrl': podcast_data.get('image_url', '')
        }

        # Save to Firebase
        save_processed_podcasts(data)

        logging.info(f"Successfully saved processed podcast to Firebase: {podcast_data['episode_title']}")

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
    logging.info(f"Fetched processed podcasts for {len(processed_podcasts['processed_podcasts'])} RSS URLs")
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

@app.route('/api/modified_rss/<path:rss_url>')
def get_modified_rss(rss_url):
    try:
        logging.info(f"Received request for modified RSS feed: {rss_url}")

        # Ensure the podcast is set for auto-processing
        save_auto_processed_podcast(rss_url)

        processed_podcasts = load_processed_podcasts()
        logging.info(f"Loaded processed podcasts for {rss_url}")

        # Ensure we're passing the correct structure to create_modified_rss_feed
        rss_specific_podcasts = processed_podcasts['processed_podcasts'].get(rss_url, [])
        logging.info(f"Found {len(rss_specific_podcasts)} processed episodes for {rss_url}")

        # Generate the modified RSS feed
        modified_rss = get_modified_rss_feed(rss_url, {rss_url: rss_specific_podcasts})

        if modified_rss:
            logging.info(f"Successfully generated modified RSS feed for {rss_url}")
            # Create a response object
            response = make_response(modified_rss)

            # Set the content type
            response.headers['Content-Type'] = 'application/xml; charset=utf-8'

            # Add cache control headers to prevent caching
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'

            return response
        else:
            logging.error(f"Failed to create modified RSS feed for {rss_url}")
            return jsonify({"error": "Failed to create modified RSS feed"}), 500
    except Exception as e:
        logging.error(f"Error in get_modified_rss for {rss_url}: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def fetch_rss_feed(rss_url):
    response = requests.get(rss_url)
    response.raise_for_status()
    return response.content

def process_episode(rss_url, episode_title, episode_url):
    # Implement the logic to process a new episode
    # This could involve downloading, transcribing, and editing the episode
    # For now, we'll just log that we would process it
    logging.info(f"Would process new episode: {episode_title} from {rss_url}")
    # In a real implementation, you would call your podcast processing function here

def save_processed_podcasts(data):
    try:
        json_data = json.dumps(data, indent=2)
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        blob.upload_from_string(json_data, content_type='application/json')
        logging.info(f"Successfully saved processed podcasts data to Firebase")
    except Exception as e:
        logging.error(f"Error saving processed podcasts data to Firebase: {str(e)}")
        logging.error(traceback.format_exc())

@app.route('/api/process', methods=['POST'])
def process_podcast():
    data = request.json
    rss_url = data.get('rss_url')
    episode_index = data.get('episode_index', 0)

    if not rss_url:
        return jsonify({"error": "Missing RSS URL"}), 400

    try:
        logging.info(f"Processing podcast with RSS URL: {rss_url}, episode index: {episode_index}")

        # Generate a job ID
        job_id = str(uuid.uuid4())

        # Use Celery to process the podcast asynchronously
        process_podcast_task.delay(rss_url, episode_index, job_id)

        return jsonify({"message": "Processing started", "job_id": job_id}), 202

    except Exception as e:
        logging.error(f"Error in process_podcast: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/process_status/<job_id>', methods=['GET'])
def get_process_status(job_id):
    status = get_job_status(job_id)
    logs = get_job_logs(job_id)
    if status:
        return jsonify({"status": status, "logs": logs})
    else:
        # If the job is not found, check if it's in the queue
        task = celery_app.AsyncResult(job_id)
        if task.state == 'PENDING':
            status = {'status': 'queued', 'progress': 0, 'stage': 'INITIALIZATION', 'message': 'Job is queued'}
        else:
            status = {'status': 'not_found', 'progress': 0, 'stage': 'UNKNOWN', 'message': 'Job not found'}
        return jsonify({"status": status, "logs": []})

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
    logging.info(f"Returning current jobs: {jobs}")
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
        processed_data = load_processed_podcasts()
        processed_podcasts = processed_data.get('processed_podcasts', {})

        if not isinstance(processed_podcasts, dict):
            logging.error(f"Expected processed_podcasts to be a dict, got {type(processed_podcasts)}")
            return jsonify({"error": "Internal server error"}), 500

        # Find and remove the podcast from the dictionary
        rss_urls_to_delete = []
        for rss_url, episodes in processed_podcasts.items():
            processed_podcasts[rss_url] = [ep for ep in episodes if not (ep['podcast_title'] == podcast_title and ep['episode_title'] == episode_title)]
            if not processed_podcasts[rss_url]:
                rss_urls_to_delete.append(rss_url)

        # Remove empty RSS URLs
        for rss_url in rss_urls_to_delete:
            del processed_podcasts[rss_url]

        # Save the updated data
        processed_data['processed_podcasts'] = processed_podcasts
        save_processed_podcasts(processed_data)

        # Delete files from Firebase Storage
        episode_folder = get_episode_folder(podcast_title, episode_title)
        for root, dirs, files in os.walk(episode_folder):
            for file in files:
                file_path = os.path.join(root, file)
                blob = storage.bucket().blob(file_path)
                if blob.exists():
                    blob.delete()
                    logging.info(f"Deleted file from Firebase Storage: {file_path}")

        # Remove the call to invalidate_rss_cache
        # invalidate_rss_cache(data.get('rss_url'))

        return jsonify({"message": "Podcast deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting processed podcast: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def save_prompt(model, prompt):
    try:
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        if blob.exists():
            json_data = blob.download_as_text()
            data = json.loads(json_data)
        else:
            data = {'processed_podcasts': []}

        if 'prompts' not in data:
            data['prompts'] = {}

        data['prompts'][model] = prompt
        json_data = json.dumps(data, indent=2)
        blob.upload_from_string(json_data, content_type='application/json')
        logging.info(f"Successfully saved {model} prompt to Firebase")
    except Exception as e:
        logging.error(f"Error saving {model} prompt to Firebase: {str(e)}")

@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    logging.info("Received request for /api/prompts")
    try:
        openai_prompt = load_prompt('openai')
        gemini_prompt = load_prompt('gemini')
        logging.info(f"Loaded prompts - OpenAI: {bool(openai_prompt)}, Gemini: {bool(gemini_prompt)}")
        return jsonify({
            'openai': openai_prompt,
            'gemini': gemini_prompt
        }), 200
    except Exception as e:
        logging.error(f"Error fetching prompts: {str(e)}")
        return jsonify({"error": "Failed to fetch prompts"}), 500

@app.route('/api/prompts', methods=['POST'])
def update_prompts():
    data = request.json
    try:
        processed_data = load_processed_podcasts()
        processed_data['prompts'] = processed_data.get('prompts', {})
        if 'openai' in data:
            processed_data['prompts']['openai'] = data['openai']
        if 'gemini' in data:
            processed_data['prompts']['gemini'] = data['gemini']
        save_processed_podcasts(processed_data)
        return jsonify({"message": "Prompts updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error updating prompts: {str(e)}")
        return jsonify({"error": "Failed to update prompts"}), 500

@app.route('/test_modified_rss', methods=['GET', 'POST'])
def test_modified_rss():
    if request.method == 'POST':
        rss_url = request.form.get('rss_url')
        if rss_url:
            response = get_modified_rss(rss_url)
            if isinstance(response, tuple) and response[1] == 202:  # Processing started
                job_id = response[0].json['job_id']
                return render_template('job_status.html', job_id=job_id, rss_url=rss_url)
            else:
                return response

    return render_template('test_modified_rss.html')

# Add this new route for auto-processing
@app.route('/api/auto_process', methods=['POST'])
def enable_auto_processing():
    data = request.json
    rss_url = data.get('rss_url')

    logging.info(f"[enable_auto_processing] Received request for RSS URL: {rss_url}")

    if not rss_url:
        logging.error("[enable_auto_processing] No RSS URL provided")
        return jsonify({'error': 'RSS URL is required'}), 400

    try:
        logging.info(f"[enable_auto_processing] Calling save_auto_processed_podcast for: {rss_url}")
        save_auto_processed_podcast(rss_url)
        logging.info(f"[enable_auto_processing] Auto-processing enabled successfully for: {rss_url}")
        return jsonify({'message': 'Auto-processing enabled successfully'}), 200
    except Exception as e:
        logging.error(f"[enable_auto_processing] Error enabling auto-processing: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': f'Failed to enable auto-processing: {str(e)}'}), 500

@app.route('/api/auto_processed_podcasts', methods=['GET'])
def get_auto_processed_podcasts():
    auto_processed_podcasts = load_auto_processed_podcasts()
    return jsonify(auto_processed_podcasts)

# Add this new route for the main page
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save_auto_processed', methods=['POST'])
def save_auto_processed():
    data = request.json
    rss_url = data.get('rss_url')

    if not rss_url:
        return jsonify({'error': 'RSS URL is required'}), 400

    try:
        logging.info(f"Received request to save auto-processed podcast: {rss_url}")
        save_auto_processed_podcast(rss_url)
        return jsonify({'message': 'Auto-processed podcast saved successfully'}), 200
    except Exception as e:
        logging.error(f"Error saving auto-processed podcast: {str(e)}")
        return jsonify({'error': 'Failed to save auto-processed podcast'}), 500

@app.route('/api/podcast_info', methods=['POST'])
def get_podcast_info():
    data = request.json
    rss_url = data.get('rss_url')
    if not rss_url:
        return jsonify({"error": "No RSS URL provided"}), 400

    try:
        processed_data = load_processed_podcasts()
        podcast_info = processed_data['podcast_info'].get(rss_url)

        if podcast_info:
            return jsonify(podcast_info), 200
        else:
            # If not found, fetch from RSS feed
            feed = feedparser.parse(rss_url)
            podcast_info = {
                "name": feed.feed.title,
                "imageUrl": feed.feed.image.href if hasattr(feed.feed, 'image') else None
            }
            return jsonify(podcast_info), 200
    except Exception as e:
        logging.error(f"Error fetching podcast info: {str(e)}")
        return jsonify({"error": "Failed to fetch podcast info"}), 500

@app.route('/api/save_podcast_info', methods=['POST'])
def save_podcast_info():
    data = request.json
    rss_url = data.get('rssUrl')
    name = data.get('name')
    image_url = data.get('imageUrl')

    if not rss_url or not name:
        return jsonify({"error": "Missing required information"}), 400

    try:
        # Load existing data
        processed_data = load_processed_podcasts()

        # Update or add podcast info
        processed_data['podcast_info'][rss_url] = {
            "name": name,
            "imageUrl": image_url
        }

        # Save updated data
        save_processed_podcasts(processed_data)

        return jsonify({"message": "Podcast info saved successfully"}), 200
    except Exception as e:
        logging.error(f"Error saving podcast info: {str(e)}")
        logging.error(traceback.format_exc())  # Add this line to get more detailed error information
        return jsonify({"error": "Failed to save podcast info"}), 500

# Add this new route to delete an auto-processed podcast
@app.route('/api/delete_auto_processed_podcast', methods=['POST', 'DELETE', 'OPTIONS'])
def delete_auto_processed_podcast():
    logging.info(f"Received request to delete auto-processed podcast. Method: {request.method}")

    if request.method == 'OPTIONS':
        logging.info("Handling OPTIONS request for delete_auto_processed_podcast")
        return '', 204

    try:
        logging.info(f"Request headers: {request.headers}")
        logging.info(f"Request data: {request.data}")

        if request.method == 'DELETE':
            # For DELETE requests, the RSS URL might be in the query parameters
            rss_url = request.args.get('rss_url')
        else:
            # For POST requests, get the RSS URL from the JSON body
            data = request.json
            rss_url = data.get('rss_url')

        logging.info(f"RSS URL to delete: {rss_url}")

        if not rss_url:
            logging.error("No RSS URL provided in the request")
            return jsonify({'error': 'RSS URL is required'}), 400

        processed_data = load_processed_podcasts()
        logging.info(f"Loaded processed data. Keys: {processed_data.keys()}")

        auto_processed = processed_data.get('auto_processed_podcasts', [])
        logging.info(f"Current auto-processed podcasts: {auto_processed}")

        # Remove the podcast from the auto-processed list
        auto_processed = [podcast for podcast in auto_processed if podcast['rss_url'] != rss_url]
        logging.info(f"Updated auto-processed podcasts: {auto_processed}")

        processed_data['auto_processed_podcasts'] = auto_processed

        # Save the updated data
        save_processed_podcasts(processed_data)

        logging.info(f"Auto-processed podcast deleted successfully: {rss_url}")
        return jsonify({'message': 'Auto-processed podcast deleted successfully'}), 200
    except Exception as e:
        logging.error(f"Error deleting auto-processed podcast: {str(e)}")
        logging.error(traceback.format_exc())
        return jsonify({'error': 'Failed to delete auto-processed podcast'}), 500

if __name__ == '__main__':
    app.run(debug=True)
