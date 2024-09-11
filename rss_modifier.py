import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import time
import logging
from functools import lru_cache
import requests
import os
from mutagen.mp3 import MP3

# Cache to store modified RSS feeds
rss_cache = {}

def get_audio_info(file_path):
    file_size = os.path.getsize(file_path)
    audio = MP3(file_path)
    duration = int(audio.info.length)
    return file_size, duration

def create_modified_rss_feed(original_rss_url, processed_podcasts, url_root):
    # Check if the cached RSS feed is still valid
    cached_rss = rss_cache.get(original_rss_url)
    if cached_rss and time.time() - cached_rss['timestamp'] < 3600:  # 1 hour cache
        return cached_rss['content']

    # If not in cache or expired, fetch the original RSS feed
    response = requests.get(original_rss_url)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch RSS feed: {response.status_code}")

    # Parse the XML content
    root = ET.fromstring(response.content)

    # Create a dictionary of processed episodes for quick lookup
    processed_episodes = {ep['rss_url']: ep for ep in processed_podcasts}

    # Find all enclosure elements in the RSS feed
    for item in root.findall('.//item'):
        enclosure = item.find('enclosure')
        if enclosure is not None:
            original_url = enclosure.get('url')

            # Check if this specific episode has been processed
            processed_episode = next((ep for ep in processed_podcasts if ep['rss_url'] == original_rss_url and ep['edited_url'].split('/')[-1].startswith(item.find('title').text.replace(' ', '_'))), None)

            if processed_episode:
                # Use the edited audio URL for the processed episode
                edited_url = urljoin(url_root, processed_episode['edited_url'])
                enclosure.set("url", edited_url)

                # Update the file size and duration
                edited_file_path = os.path.join('output', os.path.basename(processed_episode['edited_url']))
                new_size, new_duration = get_audio_info(edited_file_path)

                # Update the length attribute in the enclosure element
                enclosure.set("length", str(new_size))

                # Update the duration element
                duration_elem = item.find('.//{http://www.itunes.com/dtds/podcast-1.0.dtd}duration')
                if duration_elem is not None:
                    duration_elem.text = str(new_duration)

    # Convert the modified XML tree back to a string
    modified_rss = ET.tostring(root, encoding="unicode")

    # Cache the result
    rss_cache[original_rss_url] = {
        'content': modified_rss,
        'timestamp': time.time()
    }
    logging.info(f"Cached new modified RSS feed for {original_rss_url}")

    return modified_rss

def invalidate_rss_cache(rss_url):
    if rss_url in rss_cache:
        del rss_cache[rss_url]
        logging.info(f"Invalidated RSS cache for {rss_url}")

# Wrapper function to handle caching and invalidation
def get_or_create_modified_rss(original_rss_url, processed_podcasts, url_root):
    cached_rss = rss_cache.get(original_rss_url)
    if cached_rss and time.time() - cached_rss['timestamp'] < 3600:  # 1 hour cache
        logging.info(f"Using cached RSS feed for {original_rss_url}")
        return cached_rss['content']

    logging.info(f"Creating new modified RSS feed for {original_rss_url}")
    modified_rss = create_modified_rss_feed(original_rss_url, processed_podcasts, url_root)

    # Ensure the RSS content is properly formatted XML
    if not modified_rss.startswith('<?xml'):
        modified_rss = f'<?xml version="1.0" encoding="UTF-8"?>\n{modified_rss}'

    # Cache the result
    rss_cache[original_rss_url] = {
        'content': modified_rss,
        'timestamp': time.time()
    }

    return modified_rss
