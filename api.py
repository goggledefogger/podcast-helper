from flask import Flask, request, jsonify, render_template, Response, send_from_directory, make_response
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes
from rss_modifier import get_or_create_modified_rss, invalidate_rss_cache
import json
import os
import logging
import queue
import threading
import requests
from urllib.parse import unquote

app = Flask(__name__)

PROCESSED_PODCASTS_FILE = 'output/processed_podcasts.json'
log_queue = queue.Queue()

# Add Taddy API configuration
TADDY_API_URL = os.getenv("TADDY_API_URL", "https://api.taddy.org")
TADDY_API_KEY = os.getenv("TADDY_API_KEY")
TADDY_USER_ID = os.getenv("TADDY_USER_ID")

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_queue.put(log_entry)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
queue_handler = QueueHandler()
logger.addHandler(queue_handler)

def load_processed_podcasts():
    if os.path.exists(PROCESSED_PODCASTS_FILE):
        with open(PROCESSED_PODCASTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_processed_podcast(podcast_data):
    podcasts = load_processed_podcasts()
    # Ensure the podcast_data includes a podcast title
    if 'podcast_title' not in podcast_data:
        podcast_data['podcast_title'] = "Unknown Podcast"
    podcasts.append(podcast_data)
    with open(PROCESSED_PODCASTS_FILE, 'w') as f:
        json.dump(podcasts, f, indent=2)

# Add a new function to search podcasts using Taddy API
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
        logging.info(f"API Response: {data}")  # Log the entire response
        podcasts_data = data.get("data", {}).get("getPodcastSeries")

        if podcasts_data is None:
            logging.warning(f"No podcasts found for query: {query}")
            return []

        # If it's a dictionary, wrap it in a list
        if isinstance(podcasts_data, dict):
            podcasts = [podcasts_data]
        elif isinstance(podcasts_data, list):
            podcasts = podcasts_data
        else:
            logging.error(f"Unexpected data type for podcasts: {type(podcasts_data)}")
            return []

        logging.info(f"Found {len(podcasts)} podcasts")
        for podcast in podcasts:
            logging.info(f"Podcast: {podcast.get('name', 'Unknown')}")
        return podcasts
    else:
        logging.error(f"Error searching podcasts: {response.text}")
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_query = request.form.get('search_query')
        if search_query:
            try:
                podcasts = search_podcasts(search_query)
                logging.info(f"Found {len(podcasts)} podcasts for query: {search_query}")
                return render_template('search_results.html', podcasts=podcasts, query=search_query)
            except Exception as e:
                logging.error(f"Error in podcast search: {str(e)}")
                return render_template('index.html', error=f"An error occurred: {str(e)}")

    processed_podcasts = load_processed_podcasts()
    return render_template('index.html', podcasts=processed_podcasts)

@app.route('/process', methods=['POST'])
def process_podcast():
    rss_url = request.form.get('rss_url')
    episode_index = int(request.form.get('episode_index', 0))
    return render_template('processing.html', rss_url=rss_url, episode_index=episode_index)

@app.route('/stream')
def stream():
    def generate():
        while True:
            try:
                log_entry = log_queue.get(timeout=1)
                yield f"data: {log_entry}\n\n"
            except queue.Empty:
                yield "data: \n\n"  # Send an empty message to keep the connection alive

    return Response(generate(), mimetype='text/event-stream')

@app.route('/run_process')
def run_process():
    rss_url = request.args.get('rss_url')
    episode_index = int(request.args.get('episode_index', 0))

    def process():
        try:
            job_queue_handler = QueueHandler(job_id)
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            logging.root.addHandler(job_queue_handler)

            processing_status[job_id]['status'] = 'in_progress'
            processing_status[job_id]['start_time'] = datetime.now().isoformat()

            result = process_podcast_episode_wrapper(rss_url, episode_index, job_id)

            if isinstance(result, dict) and "error" in result:
                processing_status[job_id]['status'] = 'failed'
                processing_status[job_id]['logs'].append(f"Error: {result['error']}")
            else:
                save_processed_podcast(result)
                processing_status[job_id]['status'] = 'completed'
                processing_status[job_id]['logs'].append("Podcast processing completed successfully")

            logging.info(f"Final processing status for job {job_id}: {processing_status[job_id]}")  # Add this debug log

        except Exception as e:
            processing_status[job_id]['status'] = 'failed'
            processing_status[job_id]['logs'].append(f"Error: {str(e)}")
            logging.error(f"Error in processing thread: {str(e)}")
            logging.error(traceback.format_exc())
        finally:
            processing_status[job_id]['end_time'] = datetime.now().isoformat()
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
            logging.root.addHandler(queue_handler)

    threading.Thread(target=process).start()
    return "", 204

@app.route('/modified_rss/<path:rss_url>')
def get_modified_rss(rss_url):
    try:
        # Decode the URL-encoded rss_url
        decoded_rss_url = unquote(rss_url)

        # Check if the URL is missing a slash after 'https:'
        if decoded_rss_url.startswith('https:/') and not decoded_rss_url.startswith('https://'):
            decoded_rss_url = decoded_rss_url.replace('https:/', 'https://', 1)

        processed_podcasts = load_processed_podcasts()

        # Get the host from the request
        host = request.headers.get('Host')
        # Construct the URL root using the request scheme and host
        url_root = f"{request.scheme}://{host}/"

        modified_rss = get_or_create_modified_rss(decoded_rss_url, processed_podcasts, url_root)

        # Create a response with the XML content
        response = make_response(modified_rss)

        # Set headers to ensure proper XML rendering
        response.headers['Content-Type'] = 'application/xml; charset=utf-8'
        response.headers['X-Content-Type-Options'] = 'nosniff'

        return response
    except Exception as e:
        logging.error(f"Error generating modified RSS: {str(e)}")
        return jsonify({"error": str(e)}), 400

@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory('output', filename, as_attachment=True)

@app.route('/output/<path:podcast_title>/<path:episode_title>/<path:filename>')
def serve_episode_file(podcast_title, episode_title, filename):
    safe_podcast_title = "".join([c for c in podcast_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_episode_title = "".join([c for c in episode_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    directory = os.path.join('output', safe_podcast_title, safe_episode_title)
    return send_from_directory(directory, filename)

@app.route('/choose_episode', methods=['POST'])
def choose_episode():
    rss_url = request.form.get('rss_url')
    if rss_url:
        try:
            episodes = get_podcast_episodes(rss_url)
            return render_template('choose_episode.html', episodes=episodes, rss_url=rss_url)
        except Exception as e:
            return render_template('index.html', error=str(e))

@app.route('/output/<path:podcast_title>/images/<path:filename>')
def serve_image(podcast_title, filename):
    return send_from_directory(os.path.join('output', podcast_title, 'images'), filename)

@app.route('/api/process_status/<job_id>', methods=['GET'])
def get_process_status(job_id):
    if job_id in processing_status:
        status = processing_status[job_id]
        logging.info(f"Returning process status for job {job_id}: {status}")  # Add this debug log
        return jsonify(status)
    else:
        logging.warning(f"Job not found: {job_id}")  # Add this debug log
        return jsonify({"error": "Job not found"}), 404

if __name__ == '__main__':
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
