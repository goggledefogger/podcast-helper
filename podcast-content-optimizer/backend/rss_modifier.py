import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import time
import logging
import traceback  # Add this import
from functools import lru_cache
import requests
import os
from mutagen.mp3 import MP3
from cache import cache_get, cache_set

# Define common namespace prefixes
NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'atom': 'http://www.w3.org/2005/Atom',
    'media': 'http://search.yahoo.com/mrss/',
}

# Initialize a simple in-memory cache
rss_cache = {}

def get_audio_info(file_path):
    # Implement this function to get audio file size and duration
    # For now, we'll return placeholder values
    return 1000000, 600  # 1MB, 10 minutes

def download_image(image_url, podcast_title):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            safe_podcast_title = "".join([c for c in podcast_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            image_dir = os.path.join('output', safe_podcast_title, 'images')
            os.makedirs(image_dir, exist_ok=True)
            image_filename = os.path.join(image_dir, 'podcast_image.jpg')
            with open(image_filename, 'wb') as f:
                f.write(response.content)
            return image_filename
    except Exception as e:
        logging.error(f"Error downloading image: {str(e)}")
    return None

def create_modified_rss_feed(original_rss_url, processed_podcasts, url_root):
    logging.info(f"Creating modified RSS feed for {original_rss_url}")

    try:
        # Parse the original RSS feed
        response = requests.get(original_rss_url)
        response.raise_for_status()
        original_xml = response.text

        # Parse the XML while preserving namespaces
        ET.register_namespace('', "http://www.w3.org/2005/Atom")
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        root = ET.fromstring(original_xml)

        # Find the channel element
        channel = root.find('channel')
        if channel is None:
            logging.error("No channel element found in the RSS feed")
            return None

        # Process items
        for item in channel.findall('item'):
            enclosure = item.find('enclosure')
            if enclosure is not None:
                processed_episode = next(
                    (ep for ep in processed_podcasts
                     if ep.get('rss_url') == original_rss_url and ep.get('episode_title') == item.findtext('title')),
                    None
                )

                if processed_episode:
                    relative_path = f"output/{processed_episode['podcast_title']}/{processed_episode['episode_title']}/{os.path.basename(processed_episode['edited_url'])}"
                    edited_url = urljoin(url_root, relative_path)
                    enclosure.set('url', edited_url)

                    edited_file_path = os.path.join('output', relative_path)
                    if os.path.exists(edited_file_path):
                        new_size, new_duration = get_audio_info(edited_file_path)
                        enclosure.set('length', str(new_size))
                        duration_elem = item.find('itunes:duration', namespaces=NAMESPACES)
                        if duration_elem is not None:
                            duration_elem.text = str(new_duration)

        # Convert the modified XML tree to a string, preserving the original structure
        modified_rss = ET.tostring(root, encoding='unicode', method='xml')
        logging.info(f"Modified RSS feed created. Length: {len(modified_rss)}")
        return modified_rss
    except Exception as e:
        logging.error(f"Error in create_modified_rss_feed: {str(e)}")
        logging.error(traceback.format_exc())
        return None

def get_or_create_modified_rss(original_rss_url, processed_podcasts, url_root):
    logging.info(f"Entering get_or_create_modified_rss with URL: {original_rss_url}")
    logging.info(f"Number of processed podcasts: {len(processed_podcasts)}")
    logging.info(f"URL root: {url_root}")

    cache_key = f"modified_rss:{original_rss_url}"
    cached_rss = rss_cache.get(cache_key)

    if cached_rss and time.time() - cached_rss['timestamp'] < 3600:  # 1 hour cache
        logging.info(f"Using cached modified RSS feed for {original_rss_url}")
        return cached_rss['content']

    logging.info(f"Creating new modified RSS feed for {original_rss_url}")
    try:
        modified_rss = create_modified_rss_feed(original_rss_url, processed_podcasts, url_root)
        if not modified_rss:
            logging.error("create_modified_rss_feed returned None or empty string")
            return None

        logging.info(f"Modified RSS created successfully. Length: {len(modified_rss)}")

        # Cache the result
        rss_cache[cache_key] = {
            'content': modified_rss,
            'timestamp': time.time()
        }
        logging.info("RSS feed cached")

        return modified_rss
    except Exception as e:
        logging.error(f"Error creating modified RSS feed: {str(e)}")
        logging.error(traceback.format_exc())
        return None

def invalidate_rss_cache(rss_url):
    cache_key = f"modified_rss:{rss_url}"
    if cache_key in rss_cache:
        del rss_cache[cache_key]
    logging.info(f"Invalidated RSS cache for {rss_url}")
