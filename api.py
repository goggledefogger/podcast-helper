from flask import Flask, request, jsonify, render_template, redirect, url_for, Response, send_from_directory
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes
from rss_modifier import get_or_create_modified_rss, invalidate_rss_cache
import json
import os
import logging
import queue
import threading

app = Flask(__name__)

PROCESSED_PODCASTS_FILE = 'processed_podcasts.json'
log_queue = queue.Queue()

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
    podcasts.append(podcast_data)
    with open(PROCESSED_PODCASTS_FILE, 'w') as f:
        json.dump(podcasts, f, indent=2)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        rss_url = request.form.get('rss_url')
        if rss_url:
            try:
                episodes = get_podcast_episodes(rss_url)
                return render_template('choose_episode.html', episodes=episodes, rss_url=rss_url)
            except Exception as e:
                return render_template('index.html', error=str(e))

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
            result = process_podcast_episode(rss_url, episode_index)
            save_processed_podcast({
                "rss_url": rss_url,
                "edited_url": result['edited_url'],
                "transcript_file": result['transcript_file'],
                "unwanted_content_file": result['unwanted_content_file']
            })
            # Invalidate the RSS cache when a new episode is processed
            invalidate_rss_cache(rss_url)
            log_queue.put("Processing completed successfully.")
        except Exception as e:
            log_queue.put(f"Error: {str(e)}")

    threading.Thread(target=process).start()
    return "", 204

@app.route('/modified_rss/<path:rss_url>')
def get_modified_rss(rss_url):
    try:
        processed_podcasts = load_processed_podcasts()
        modified_rss = get_or_create_modified_rss(rss_url, processed_podcasts, request.url_root)
        return modified_rss, 200, {'Content-Type': 'application/rss+xml'}
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory('output', filename)

if __name__ == '__main__':
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
