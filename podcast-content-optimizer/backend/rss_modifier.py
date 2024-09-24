import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin, quote
import time
import logging
import traceback
from functools import lru_cache
import requests
import os
from mutagen.mp3 import MP3
from cache import cache_get, cache_set
from utils import format_duration
from flask import request
from io import StringIO
from utils import safe_filename
import urllib.parse
from firebase_admin import storage

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
    audio = MP3(file_path)
    return audio.info.filesize, audio.info.length  # Returns (file_size, duration_in_seconds)

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

def create_modified_rss_feed(original_rss_url, processed_podcasts):
    logging.info(f"Creating modified RSS feed for {original_rss_url}")

    try:
        # Parse the original RSS feed
        response = requests.get(original_rss_url)
        response.raise_for_status()
        original_xml = response.text

        # Parse the XML while preserving namespaces
        root = ET.fromstring(original_xml)

        # Collect all namespaces used in the document
        namespaces = dict([node for _, node in ET.iterparse(StringIO(original_xml), events=['start-ns'])])

        # Update our NAMESPACES dictionary with the collected namespaces
        NAMESPACES.update(namespaces)

        # Register all namespaces
        for prefix, uri in NAMESPACES.items():
            ET.register_namespace(prefix, uri)

        # Find the channel element
        channel = root.find('channel')
        if channel is None:
            logging.error("No channel element found in the RSS feed")
            return None

        # Get the current URL root from the request
        url_root = request.url_root.rstrip('/')

        # Properly encode the entire original RSS URL
        encoded_rss_url = quote(original_rss_url, safe='')

        # Update <itunes:new-feed-url> if it exists
        new_feed_url = channel.find('itunes:new-feed-url', namespaces=NAMESPACES)
        if new_feed_url is not None:
            new_feed_url.text = f"{url_root}/api/modified_rss/{quote(original_rss_url, safe='')}"

        # Update <atom:link rel="self"> if it exists
        atom_link = channel.find('atom:link[@rel="self"]', namespaces=NAMESPACES)
        if atom_link is not None:
            atom_link.set('href', f"{url_root}/api/modified_rss/{quote(original_rss_url, safe='')}")

        # Update the channel title
        title_elem = channel.find('title')
        if title_elem is not None:
            title_elem.text = f"{title_elem.text} (Optimized)"

        # Update the channel description
        description_elem = channel.find('description')
        if description_elem is not None:
            description_elem.text = f"Optimized version: {description_elem.text}"

        # Generate a new unique feed GUID
        channel_guid = channel.find('guid')
        if channel_guid is not None:
            channel_guid.text = f"optimized_feed_{int(time.time())}"
        else:
            channel_guid = ET.SubElement(channel, 'guid')
            channel_guid.text = f"optimized_feed_{int(time.time())}"
        channel_guid.set('isPermaLink', 'false')

        # Update iTunes specific elements
        itunes_author = channel.find('itunes:author', namespaces=NAMESPACES)
        if itunes_author is not None:
            itunes_author.text = f"{itunes_author.text} (Optimized)"

        itunes_title = channel.find('itunes:title', namespaces=NAMESPACES)
        if itunes_title is not None:
            itunes_title.text = f"{itunes_title.text} (Optimized)"

        # Update the link to point to your modified RSS feed
        link_elem = channel.find('link')
        if link_elem is not None:
            link_elem.text = f"{url_root}/api/modified_rss/{quote(original_rss_url, safe='')}"

        # Update or add a new <itunes:new-feed-url> element
        # Update the description to mention it's a modified feed
        description_elem = channel.find('description')
        if description_elem is not None:
            description_elem.text = f"Modified version: {description_elem.text}"

        # Generate a new unique feed GUID
        guid_elem = channel.find('guid')
        if guid_elem is not None:
            guid_elem.text = f"{guid_elem.text}_modified_{int(time.time())}"

        # Update or add a new <itunes:new-feed-url> element
        new_feed_url = channel.find('itunes:new-feed-url', namespaces=NAMESPACES)
        if new_feed_url is None:
            new_feed_url = ET.SubElement(channel, f"{{{NAMESPACES['itunes']}}}new-feed-url")
        new_feed_url.text = f"{url_root}/api/modified_rss/{quote(original_rss_url, safe='')}"

        # Update the <atom:link> element
        atom_link = channel.find('atom:link[@rel="self"]', namespaces=NAMESPACES)
        if atom_link is not None:
            atom_link.set('href', f"{url_root}/api/modified_rss/{quote(original_rss_url, safe='')}")
        else:
            atom_link = ET.SubElement(channel, f"{{{NAMESPACES['atom']}}}link", attrib={
                'href': f"{url_root}/api/modified_rss/{quote(original_rss_url, safe='')}",
                'rel': 'self',
                'type': 'application/rss+xml'
            })

        # # Add this near the top of the function
        # image_elem = channel.find('image')
        # if image_elem is not None:
        #     url_elem = image_elem.find('url')
        #     if url_elem is not None:
        #         url_elem.text = f"{url_root}/static/optimized_podcast_image.jpg"

        # itunes_image = channel.find('itunes:image', namespaces=NAMESPACES)
        # if itunes_image is not None:
        #     itunes_image.set('href', f"{url_root}/static/optimized_podcast_image.jpg")

        # Process items
        for item in channel.findall('item'):
            item_title = item.find('title')
            if item_title is not None:
                # Check if this episode has been processed
                processed_episode = next(
                    (ep for ep in processed_podcasts
                     if ep.get('rss_url') == original_rss_url and ep.get('episode_title') == item_title.text),
                    None
                )

                if processed_episode:
                    # Only add "(Optimized)" if the episode has been processed
                    item_title.text = f"{item_title.text} (Optimized)"

                    # Update other elements for processed episodes
                    guid = item.find('guid')
                    if guid is not None:
                        guid.text = f"{guid.text}_optimized"

                    pub_date = item.find('pubDate')
                    if pub_date is not None:
                        pub_date.text = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())

                    itunes_title = item.find('itunes:title', namespaces=NAMESPACES)
                    if itunes_title is not None:
                        itunes_title.text = f"{itunes_title.text} (Optimized)"

                    enclosure = item.find('enclosure')
                    if enclosure is not None:
                        # Use the Firebase Storage URL directly
                        enclosure.set('url', processed_episode['edited_url'])

                        duration_elem = item.find('itunes:duration', namespaces=NAMESPACES)
                        if duration_elem is not None:
                            duration_elem.text = format_duration(new_duration)

        # Update namespace-specific identifiers
        for prefix, uri in namespaces.items():
            for id_type in ['organizationId', 'networkId', 'programId']:
                id_elem = channel.find(f'{{{uri}}}{id_type}')
                if id_elem is not None:
                    id_elem.text = f"{id_elem.text}_modified"

        # Convert the modified XML tree to a string, preserving the original structure
        modified_rss = ET.tostring(root, encoding='unicode', method='xml')
        logging.info(f"Modified RSS feed created. Length: {len(modified_rss)}")
        return modified_rss
    except Exception as e:
        logging.error(f"Error in create_modified_rss_feed: {str(e)}")
        logging.error(traceback.format_exc())
        return None

def get_or_create_modified_rss(original_rss_url, processed_podcasts):
    logging.info(f"Entering get_or_create_modified_rss with URL: {original_rss_url}")
    logging.info(f"Number of processed podcasts: {len(processed_podcasts)}")

    cache_key = f"modified_rss:{original_rss_url}"
    cached_rss = rss_cache.get(cache_key)

    if cached_rss and time.time() - cached_rss['timestamp'] < 3600:  # 1 hour cache
        logging.info(f"Using cached modified RSS feed for {original_rss_url}")
        return cached_rss['content']

    logging.info(f"Creating new modified RSS feed for {original_rss_url}")
    try:
        modified_rss = create_modified_rss_feed(original_rss_url, processed_podcasts)
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
