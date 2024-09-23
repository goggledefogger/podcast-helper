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

PROCESSED_PODCASTS_FILE = 'output/processed_podcasts.json'

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
    if os.path.exists(PROCESSED_PODCASTS_FILE):
        with open(PROCESSED_PODCASTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_processed_podcast(podcast_data):
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(PROCESSED_PODCASTS_FILE), exist_ok=True)

        # Load existing data or create an empty list
        if os.path.exists(PROCESSED_PODCASTS_FILE):
            with open(PROCESSED_PODCASTS_FILE, 'r') as f:
                podcasts = json.load(f)
        else:
            podcasts = []

        # Check if the podcast already exists in the list
        existing_podcast = next((p for p in podcasts if p['rss_url'] == podcast_data['rss_url'] and p['episode_title'] == podcast_data['episode_title']), None)

        if existing_podcast:
            # Update the existing podcast data
            existing_podcast.update(podcast_data)
        else:
            # Append new data
            podcasts.append(podcast_data)

        # Convert file paths to URLs
        for key in ['edited_url', 'transcript_file', 'unwanted_content_file', 'input_file', 'output_file']:
            if key in podcast_data and podcast_data[key]:
                if os.path.exists(podcast_data[key]):
                    podcast_data[key] = file_path_to_url(podcast_data[key])
                else:
                    logging.warning(f"File not found: {podcast_data[key]}")

        logging.info(f"Saving processed podcast: {podcast_data}")

        # Write updated data
        with open(PROCESSED_PODCASTS_FILE, 'w') as f:
            json.dump(podcasts, f, indent=2)

        logging.info(f"Saved processed podcast to {PROCESSED_PODCASTS_FILE}")

    except Exception as e:
        logging.error(f"Error saving processed podcast: {str(e)}")
        logging.error(traceback.format_exc())

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
    # Remove the base output directory from the path
    relative_path = os.path.relpath(file_path, 'output')
    # Convert backslashes to forward slashes for Windows compatibility
    relative_path = relative_path.replace('\\', '/')
    # URL encode each path component
    encoded_path = '/'.join(urllib.parse.quote(component) for component in relative_path.split('/'))
    # Always start with "/output/"
    return f"/output/{encoded_path}"

def get_episode_folder(podcast_title, episode_title):
    safe_podcast_title = safe_filename(podcast_title)
    safe_episode_title = safe_filename(episode_title)
    return os.path.join('output', safe_podcast_title, safe_episode_title)