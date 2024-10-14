import feedparser
import requests
from tqdm import tqdm
import logging
import traceback
import time
import sys
from mutagen.mp3 import MP3
import json
import os
import urllib.parse
import re
import firebase_admin
from firebase_admin import credentials, storage
import redis

# Initialize Firebase app
cred = credentials.Certificate('etc/firebaseServiceAccountKey.json')
firebase_admin.initialize_app(cred, {
    'storageBucket': 'podcast-helper-435105.appspot.com'
})

bucket = storage.bucket()

# Update this constant
PROCESSED_PODCASTS_FILE = 'db.json'

def get_podcast_episodes(rss_url):
    try:
        logging.info(f"Parsing RSS feed: {rss_url}")
        feed = feedparser.parse(rss_url)

        if feed.bozo:
            logging.error(f"Error parsing RSS feed: {feed.bozo_exception}")
            raise ValueError(f"Invalid RSS feed: {feed.bozo_exception}")

        if not feed.entries:
            logging.warning(f"No entries found in the RSS feed: {rss_url}")
            return []

        podcast_title = feed.feed.get('title', 'Unknown Podcast')
        episodes = []
        for i, entry in enumerate(feed.entries):
            episode = {
                'number': i + 1,
                'title': entry.get('title', 'Untitled'),
                'published': entry.get('published', 'Unknown date'),
                'podcast_title': podcast_title,
                'url': entry.get('enclosures', [{}])[0].get('href') or entry.get('link'),
                'duration': get_episode_duration(entry)
            }
            if not episode['url']:
                logging.warning(f"No URL found for episode: {episode['title']}")
            episodes.append(episode)

        logging.info(f"Successfully parsed {len(episodes)} episodes")
        return episodes
    except Exception as e:
        logging.error(f"Error in get_podcast_episodes: {str(e)}")
        logging.error(traceback.format_exc())
        raise ValueError(f"Failed to parse podcast episodes: {str(e)}")

def get_episode_duration(entry):
    # Try to get duration from the RSS feed
    duration = entry.get('itunes_duration')
    if duration:
        return parse_duration(duration)

    # If not available, try to get it from the audio file (if accessible)
    audio_url = entry.get('enclosures', [{}])[0].get('href')
    if audio_url:
        try:
            audio = MP3(audio_url)
            return audio.info.length
        except:
            pass

    # If all else fails, return None
    return None

def download_episode(url, filename):
    try:
        logging.info(f"Starting download from URL: {url}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes

        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192  # 8 KB

        logging.info(f"Total file size: {total_size} bytes")

        with open(filename, 'wb') as file, tqdm(
            desc=filename,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as progress_bar:
            downloaded = 0
            for data in response.iter_content(block_size):
                size = file.write(data)
                downloaded += size
                progress_bar.update(size)

                # Log progress every 10%
                if total_size > 0 and downloaded % (total_size // 10) < block_size:
                    percent = (downloaded / total_size) * 100
                    logging.info(f"Download progress: {percent:.2f}%")

        if total_size != 0 and downloaded != total_size:
            logging.warning(f"Downloaded {downloaded} bytes, expected {total_size} bytes.")
        else:
            logging.info("Download completed successfully.")

    except requests.exceptions.RequestException as e:
        logging.error(f"Error downloading episode: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error during download: {str(e)}")
        raise

def run_with_animation(func, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        logging.info(f"Function {func.__name__} completed successfully")
        return result
    except Exception as e:
        logging.error(f"Error in {func.__name__}: {str(e)}")
        logging.error(traceback.format_exc())
        raise

def load_processed_podcasts():
    try:
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        if blob.exists():
            json_data = blob.download_as_text()
            data = json.loads(json_data)
            if not isinstance(data, dict):
                data = {'processed_podcasts': {}, 'auto_processed_podcasts': [], 'podcast_info': {}, 'prompts': {}}
            return data
        else:
            return {'processed_podcasts': {}, 'auto_processed_podcasts': [], 'podcast_info': {}, 'prompts': {}}
    except Exception as e:
        logging.error(f"Error loading processed podcasts from Firebase: {str(e)}")
        logging.error(traceback.format_exc())
        return {'processed_podcasts': {}, 'auto_processed_podcasts': [], 'podcast_info': {}, 'prompts': {}}

def save_processed_podcasts(data):
    try:
        json_data = json.dumps(data, indent=2)
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        blob.upload_from_string(json_data, content_type='application/json')
        logging.info(f"Successfully saved processed podcasts data to Firebase")
    except Exception as e:
        logging.error(f"Error saving processed podcasts data to Firebase: {str(e)}")
        logging.error(traceback.format_exc())

def save_auto_processed_podcasts(auto_processed_podcasts):
    try:
        data = load_processed_podcasts()
        data['auto_processed_podcasts'] = auto_processed_podcasts
        save_processed_podcasts(data)
        logging.info(f"Successfully saved auto-processed podcasts to Firebase")
    except Exception as e:
        logging.error(f"Error saving auto-processed podcasts to Firebase: {str(e)}")
        logging.error(traceback.format_exc())
        raise

def parse_duration(duration):
    """
    Parse a time string into seconds.
    Accepts:
    - "HH:MM:SS" format
    - "MM:SS" format
    - Seconds as a string (e.g., "83.5")
    - Seconds as a float or int
    Returns: Seconds as float
    """
    if isinstance(duration, (float, int)):
        return float(duration)

    if isinstance(duration, str):
        # Try to parse as a decimal number first
        try:
            return float(duration)
        except ValueError:
            pass

        # If not a decimal, try to parse as HH:MM:SS or MM:SS
        parts = duration.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)

    # If we get here, the format is invalid
    raise ValueError(f"Invalid duration format: {duration}")

def format_duration(seconds: float, format: str = 'HH:MM:SS') -> str:
    """
    Format duration in seconds to a string.
    Formats:
    - 'HH:MM:SS'
    - 'MM:SS'
    - 'SS'
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    if format == 'HH:MM:SS':
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    elif format == 'MM:SS':
        return f"{minutes:02d}:{seconds:02d}"
    elif format == 'SS':
        return str(int(seconds))
    else:
        raise ValueError(f"Invalid format: {format}")

def safe_filename(filename):
    # Replace spaces and colons with underscores, remove other non-alphanumeric characters
    return re.sub(r'[^\w\-_\. ]', '', filename.replace(' ', '_').replace(':', '_'))

def encode_url_path(component):
    return urllib.parse.quote(component)

def decode_url_path(encoded_path):
    return urllib.parse.unquote(encoded_path)

def url_to_file_path(url_path, base_dir='output'):
    logging.info(f"Converting URL path to file path: {url_path}")
    decoded_path = decode_url_path(url_path)
    path_components = decoded_path.split('/')
    safe_components = [safe_filename(component) for component in path_components]
    safe_path = os.path.join(*safe_components)
    full_path = os.path.join(base_dir, safe_path)
    logging.info(f"Converted to file path: {full_path}")
    return full_path

def file_path_to_url(file_path):
    return upload_to_firebase(file_path)

def get_episode_folder(podcast_title, episode_title):
    safe_podcast_title = safe_filename(podcast_title)
    safe_episode_title = safe_filename(episode_title)
    return os.path.join('output', safe_podcast_title, safe_episode_title)

def upload_to_firebase(file_path, delete_local=True):
    try:
        # Check if the file_path is already a URL
        if file_path.startswith('http://') or file_path.startswith('https://'):
            logging.info(f"File is already a URL, skipping upload: {file_path}")
            return file_path

        # Ensure the file exists locally
        if not os.path.exists(file_path):
            logging.error(f"File does not exist locally: {file_path}")
            return None

        # Generate a storage path (you might want to adjust this logic)
        storage_path = os.path.relpath(file_path, 'output')
        blob = bucket.blob(storage_path)

        logging.info(f"Uploading file to Firebase: {file_path}")
        blob.upload_from_filename(file_path)

        # Make the file public
        blob.make_public()

        public_url = blob.public_url
        logging.info(f"Successfully uploaded and made public file in Firebase: {file_path} -> {public_url}")

        # Delete the local file if requested
        if delete_local:
            try:
                os.remove(file_path)
                logging.info(f"Deleted local file after upload: {file_path}")
            except Exception as delete_error:
                logging.warning(f"Failed to delete local file after upload: {file_path}. Error: {str(delete_error)}")

        return public_url
    except Exception as e:
        logging.error(f"Error uploading file to Firebase: {file_path}, Error: {str(e)}")
        return None

def file_exists_in_firebase(file_path):
    # Remove the bucket name from the beginning of the path if it's there
    bucket_name = 'podcast-helper-435105.appspot.com'
    if file_path.startswith(bucket_name):
        file_path = file_path[len(bucket_name):].lstrip('/')

    blob = bucket.blob(file_path)
    exists = blob.exists()
    logging.info(f"Checking if file exists in Firebase: {file_path}, Result: {exists}")
    return exists

def download_from_firebase(firebase_url, local_path):
    try:
        # Extract the path from the Firebase URL
        parsed_url = urllib.parse.urlparse(firebase_url)
        file_path = parsed_url.path.lstrip('/')

        # Remove the bucket name from the beginning of the path if it's there
        bucket_name = 'podcast-helper-435105.appspot.com'
        if file_path.startswith(bucket_name):
            file_path = file_path[len(bucket_name):].lstrip('/')

        logging.info(f"Attempting to download file from Firebase: {file_path}")

        blob = bucket.blob(file_path)

        if not blob.exists():
            logging.error(f"File does not exist in Firebase Storage: {file_path}")
            return False

        blob.download_to_filename(local_path)
        logging.info(f"Successfully downloaded file from Firebase: {firebase_url} -> {local_path}")
        return True
    except Exception as e:
        logging.error(f"Error downloading file from Firebase: {firebase_url}, Error: {str(e)}")
        logging.error(traceback.format_exc())
        return False

def load_auto_processed_podcasts():
    data = load_processed_podcasts()
    if isinstance(data, dict):
        auto_processed = data.get('auto_processed_podcasts', [])
    elif isinstance(data, list):
        # If data is a list, it's likely the old format where auto-processed podcasts weren't stored
        auto_processed = []
    else:
        logging.error(f"Unexpected data type in load_processed_podcasts: {type(data)}")
        auto_processed = []
    return list(auto_processed) if auto_processed is not None else []

def is_episode_processed(rss_url, episode_title):
    processed_podcasts = load_processed_podcasts()
    return any(
        episode['episode_title'] == episode_title
        for episode in processed_podcasts['processed_podcasts'].get(rss_url, [])
    )

def get_db():
    if not hasattr(get_db, 'db'):
        get_db.db = redis.Redis(host='localhost', port=6379, db=0)
    return get_db.db

def save_processed_podcast(podcast_data):
    try:
        data = load_processed_podcasts()
        rss_url = podcast_data['rss_url']

        if rss_url not in data['processed_podcasts']:
            data['processed_podcasts'][rss_url] = []

        # Check if the episode already exists
        existing_episode = next((ep for ep in data['processed_podcasts'][rss_url] if ep['episode_title'] == podcast_data['episode_title']), None)

        if existing_episode:
            existing_episode.update(podcast_data)
        else:
            data['processed_podcasts'][rss_url].append(podcast_data)

        # Update podcast info, preserving the existing image URL if not provided in podcast_data
        if rss_url not in data['podcast_info']:
            data['podcast_info'][rss_url] = {}

        data['podcast_info'][rss_url]['name'] = podcast_data['podcast_title']
        if 'image_url' in podcast_data and podcast_data['image_url']:
            data['podcast_info'][rss_url]['imageUrl'] = podcast_data['image_url']
        elif 'imageUrl' not in data['podcast_info'][rss_url]:
            data['podcast_info'][rss_url]['imageUrl'] = ''

        # Save to Firebase
        save_processed_podcasts(data)

        logging.info(f"Successfully saved processed podcast to Firebase: {podcast_data['episode_title']}")
    except Exception as e:
        logging.error(f"Error saving processed podcast to Firebase: {str(e)}")
        logging.error(traceback.format_exc())
