from flask import Flask, request, jsonify, render_template, redirect, url_for
from podcast_processor import process_podcast_episode
from rss_modifier import create_modified_rss_feed
import json
import os

app = Flask(__name__)

PROCESSED_PODCASTS_FILE = 'processed_podcasts.json'

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
                result = process_podcast_episode(rss_url, 0)
                save_processed_podcast({
                    "rss_url": rss_url,
                    "edited_url": result['edited_url'],
                    "transcript_file": result['transcript_file'],
                    "unwanted_content_file": result['unwanted_content_file']
                })
                return redirect(url_for('index'))
            except Exception as e:
                return jsonify({"error": str(e)}), 400

    processed_podcasts = load_processed_podcasts()
    return render_template('index.html', podcasts=processed_podcasts)

@app.route('/process', methods=['POST'])
def process_podcast():
    data = request.json
    rss_url = data.get('rss_url')
    episode_index = data.get('episode_index', 0)

    if not rss_url:
        return jsonify({"error": "RSS URL is required"}), 400

    try:
        result = process_podcast_episode(rss_url, episode_index)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/modified_rss/<path:rss_url>')
def get_modified_rss(rss_url):
    try:
        modified_rss = create_modified_rss_feed(rss_url)
        return modified_rss, 200, {'Content-Type': 'application/rss+xml'}
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
