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
from datetime import datetime, timezone, timedelta
import threading

# Global variable to hold the Firebase app
firebase_app = None
firebase_init_lock = threading.Lock()

def initialize_firebase():
    global firebase_app
    if firebase_app is None:
        with firebase_init_lock:
            if firebase_app is None:
                try:
                    cred = credentials.Certificate('etc/firebaseServiceAccountKey.json')
                    firebase_app = firebase_admin.initialize_app(cred, {
                        'storageBucket': 'podcast-helper-435105.appspot.com'
                    })
                except ValueError as e:
                    if "The default Firebase app already exists" in str(e):
                        firebase_app = firebase_admin.get_app()
                    else:
                        raise
    return firebase_app

def get_storage_bucket():
    try:
        return storage.bucket()
    except ValueError:
        initialize_firebase()
        return storage.bucket()

# Update this constant
PROCESSED_PODCASTS_FILE = 'db.json'

def get_podcast_episodes(rss_url):
    try:
        logging.info(f"Parsing RSS feed: {rss_url}")

        # First attempt: Parse the feed normally
        feed = feedparser.parse(rss_url)

        # If there's an encoding error, try parsing with explicit encodings
        if feed.bozo and isinstance(feed.bozo_exception, feedparser.CharacterEncodingOverride):
            logging.warning(f"Encoding mismatch detected. Attempting to parse with different encodings: {rss_url}")

            for encoding in ['utf-8', 'ascii', 'iso-8859-1']:
                try:
                    response = requests.get(rss_url)
                    response.encoding = encoding
                    feed = feedparser.parse(response.text)
                    if not feed.bozo:
                        logging.info(f"Successfully parsed feed with {encoding} encoding")
                        break
                except Exception as e:
                    logging.warning(f"Failed to parse with {encoding} encoding: {str(e)}")

        if feed.bozo and not isinstance(feed.bozo_exception, feedparser.CharacterEncodingOverride):
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
                'url': entry.get('enclosures', [{}])[0].get('href') or entry.get('link', ''),
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
            logging.debug(f"Loaded processed podcasts data: {json.dumps(data, indent=2)}")
            return data
        else:
            logging.warning(f"File {PROCESSED_PODCASTS_FILE} does not exist in Firebase Storage")
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
        logging.info(f"[save_processed_podcasts] Successfully saved processed podcasts data to Firebase")
        logging.debug(f"[save_processed_podcasts] Saved data: {json_data}")
    except Exception as e:
        logging.error(f"[save_processed_podcasts] Error saving processed podcasts data to Firebase: {str(e)}")
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
    if file_path.startswith('http://') or file_path.startswith('https://'):
        logging.info(f"File is already a URL, skipping upload: {file_path}")
        return file_path

    if not os.path.exists(file_path):
        logging.error(f"File does not exist locally: {file_path}")
        return None

    try:
        bucket = get_storage_bucket()
        storage_path = os.path.relpath(file_path, 'output')
        blob = bucket.blob(storage_path)
        blob.upload_from_filename(file_path)
        blob.make_public()
        public_url = blob.public_url
        logging.info(f"Successfully uploaded and made public file in Firebase: {file_path} -> {public_url}")

        if delete_local:
            os.remove(file_path)
            logging.info(f"Deleted local file after upload: {file_path}")

        return public_url
    except Exception as e:
        logging.error(f"Error uploading file to Firebase: {file_path}, Error: {str(e)}")
        return None

def file_exists_in_firebase(file_path):
    # Remove the bucket name from the beginning of the path if it's there
    bucket_name = 'podcast-helper-435105.appspot.com'
    if file_path.startswith(bucket_name):
        file_path = file_path[len(bucket_name):].lstrip('/')

    bucket = get_storage_bucket()
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

        bucket = get_storage_bucket()
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
    return data.get('auto_processed_podcasts', [])

def save_auto_processed_podcast(rss_url):
    try:
        logging.info(f"[save_auto_processed_podcast] Starting for RSS URL: {rss_url}")
        data = load_processed_podcasts()
        logging.debug(f"[save_auto_processed_podcast] Loaded data: {json.dumps(data, indent=2)}")

        auto_processed = data.get('auto_processed_podcasts', [])
        logging.debug(f"[save_auto_processed_podcast] Current auto_processed_podcasts: {auto_processed}")

        current_time = datetime.now(timezone.utc).isoformat()

        # Check if the RSS URL is already in the list
        existing_entry = next((item for item in auto_processed if item['rss_url'] == rss_url), None)

        if existing_entry:
            logging.info(f"[save_auto_processed_podcast] Updating existing entry for {rss_url}")
            existing_entry['enabled_at'] = current_time
            existing_entry['last_checked_at'] = current_time
            logging.debug(f"[save_auto_processed_podcast] Updated existing entry: {existing_entry}")
        else:
            logging.info(f"[save_auto_processed_podcast] Adding new entry for {rss_url}")
            new_entry = {
                'rss_url': rss_url,
                'enabled_at': current_time,
                'last_checked_at': current_time
            }
            auto_processed.append(new_entry)
            logging.debug(f"[save_auto_processed_podcast] Added new entry: {new_entry}")

        # Always fetch and update podcast information
        try:
            feed = feedparser.parse(rss_url)
            podcast_title = feed.feed.get('title', 'Unknown Podcast')
            podcast_image = feed.feed.get('image', {}).get('href', '')

            if 'podcast_info' not in data:
                data['podcast_info'] = {}

            data['podcast_info'][rss_url] = {
                'name': podcast_title,
                'imageUrl': podcast_image
            }
            logging.info(f"[save_auto_processed_podcast] Updated podcast info for {rss_url}")
            logging.debug(f"[save_auto_processed_podcast] New podcast info: {data['podcast_info'][rss_url]}")
        except Exception as e:
            logging.error(f"[save_auto_processed_podcast] Error fetching podcast info: {str(e)}")
            logging.error(traceback.format_exc())

        data['auto_processed_podcasts'] = auto_processed
        logging.debug(f"[save_auto_processed_podcast] Data after modification: {json.dumps(data, indent=2)}")

        save_processed_podcasts(data)
        logging.info(f"[save_auto_processed_podcast] Auto-processed podcast saved successfully: {rss_url}")
    except Exception as e:
        logging.error(f"[save_auto_processed_podcast] Error saving auto-processed podcast: {str(e)}")
        logging.error(traceback.format_exc())
        raise

def get_auto_process_enable_date(rss_url):
    data = load_processed_podcasts()
    auto_processed = data.get('auto_processed_podcasts', [])

    logging.info(f"Checking auto-process enable date for RSS URL: {rss_url}")
    logging.info(f"Auto-processed podcasts: {json.dumps(auto_processed, indent=2)}")

    entry = next((item for item in auto_processed if item['rss_url'] == rss_url), None)

    if entry and 'enabled_at' in entry:
        enable_date = datetime.fromisoformat(entry['enabled_at'])
        logging.info(f"Found enable date for {rss_url}: {enable_date}")
        return enable_date
    else:
        logging.warning(f"No enable date found for {rss_url}")
        return None

def is_episode_new(original_rss_url, episode_published_date):
    enable_date = get_auto_process_enable_date(original_rss_url)
    if enable_date is None:
        return False
    # Ensure both dates are timezone-aware
    if enable_date.tzinfo is None:
        enable_date = enable_date.replace(tzinfo=timezone.utc)
    if episode_published_date.tzinfo is None:
        episode_published_date = episode_published_date.replace(tzinfo=timezone.utc)
    return episode_published_date >= enable_date

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
            data['podcast_info'] = {}

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

def is_episode_processed(rss_url, episode_title):
    processed_podcasts = load_processed_podcasts()
    rss_episodes = processed_podcasts['processed_podcasts'].get(rss_url, [])
    return any(
        episode['episode_title'] == episode_title and
        episode.get('status') == 'completed'  # Only check for completed status
        for episode in rss_episodes
    )

def is_episode_being_processed(rss_url, episode_title):
    try:
        db = get_db()

        # Check for active processing lock
        lock_key = f"lock:job:{rss_url}:{episode_title}"
        if db.exists(lock_key):
            # Verify the lock hasn't expired
            ttl = db.ttl(lock_key)
            if ttl > 0:
                return True
            else:
                # Clean up expired lock
                db.delete(lock_key)
                return False

        # Check job status
        status_key = f"job_status:{rss_url}:{episode_title}"
        if db.exists(status_key):
            status = db.get(status_key)
            if status:
                status = json.loads(status)
                # Only return True if the job is actually in progress
                return status.get('status') in ['processing', 'pending']

        return False
    except Exception as e:
        logging.error(f"Error checking if episode is being processed: {str(e)}")
        return False

def get_db():
    if not hasattr(get_db, 'db'):
        get_db.db = redis.Redis(host='localhost', port=6379, db=0)
    return get_db.db
