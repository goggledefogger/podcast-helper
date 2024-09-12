import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import time
import logging
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

    # Parse the original RSS feed
    feed = feedparser.parse(original_rss_url)

    # Create a new RSS feed
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')

    # Copy channel-level elements
    for elem in feed.feed:
        if elem not in ('items', 'links'):
            ET.SubElement(channel, elem).text = str(feed.feed[elem])

    # Handle image
    if 'image' in feed.feed:
        image_url = feed.feed.image.get('href') or feed.feed.image.get('url')
        if image_url:
            local_image_path = download_image(image_url, feed.feed.title)
            if local_image_path:
                image_elem = ET.SubElement(channel, 'image')
                ET.SubElement(image_elem, 'url').text = urljoin(url_root, local_image_path)
                ET.SubElement(image_elem, 'title').text = feed.feed.title
                ET.SubElement(image_elem, 'link').text = feed.feed.link

    # Process items
    for item in feed.entries:
        new_item = ET.SubElement(channel, 'item')
        for elem in item:
            if elem not in ('links'):
                ET.SubElement(new_item, elem).text = str(item[elem])

        # Handle enclosure
        for link in item.links:
            if link.rel == 'enclosure':
                enclosure = ET.SubElement(new_item, 'enclosure')
                processed_episode = next((ep for ep in processed_podcasts if ep['rss_url'] == original_rss_url and ep['episode_title'] == item.title), None)

                if processed_episode:
                    relative_path = f"output/{processed_episode['podcast_title']}/{processed_episode['episode_title']}/{os.path.basename(processed_episode['edited_url'])}"
                    edited_url = urljoin(url_root, relative_path)
                    enclosure.set('url', edited_url)

                    edited_file_path = os.path.join('output', relative_path)
                    if os.path.exists(edited_file_path):
                        new_size, new_duration = get_audio_info(edited_file_path)
                        enclosure.set('length', str(new_size))
                        duration_elem = new_item.find('itunes:duration', namespaces=NAMESPACES)
                        if duration_elem is not None:
                            duration_elem.text = str(new_duration)
                else:
                    enclosure.set('url', link.href)
                    enclosure.set('type', link.type)
                    enclosure.set('length', str(link.length))

    # Convert the modified XML tree to a string
    modified_rss = ET.tostring(rss, encoding='unicode')
    return modified_rss

def get_or_create_modified_rss(original_rss_url, processed_podcasts, url_root):
    cache_key = f"modified_rss:{original_rss_url}"
    cached_rss = rss_cache.get(cache_key)

    if cached_rss and time.time() - cached_rss['timestamp'] < 3600:  # 1 hour cache
        logging.info(f"Using cached modified RSS feed for {original_rss_url}")
        return cached_rss['content']

    logging.info(f"Creating new modified RSS feed for {original_rss_url}")
    modified_rss = create_modified_rss_feed(original_rss_url, processed_podcasts, url_root)

    # Cache the result
    rss_cache[cache_key] = {
        'content': modified_rss,
        'timestamp': time.time()
    }

    return modified_rss

def invalidate_rss_cache(rss_url):
    cache_key = f"modified_rss:{rss_url}"
    if cache_key in rss_cache:
        del rss_cache[cache_key]
    logging.info(f"Invalidated RSS cache for {rss_url}")
