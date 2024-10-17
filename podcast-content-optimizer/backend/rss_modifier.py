import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin, quote
import time
import logging
import traceback
import requests
import os
from mutagen.mp3 import MP3
from utils import format_duration, is_episode_processed, is_episode_being_processed, get_podcast_episodes, is_episode_new, get_auto_process_enable_date
from flask import request
from io import StringIO
from utils import safe_filename
import urllib.parse
from firebase_admin import storage
import json
from podcast_processor import process_podcast_episode
from api.tasks import process_podcast_task
import uuid
from datetime import datetime, timezone

# Define common namespace prefixes
NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'atom': 'http://www.w3.org/2005/Atom',
    'media': 'http://search.yahoo.com/mrss/',
}

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
            new_feed_url.text = f"{url_root}/api/modified_rss/{encoded_rss_url}"

        # Update <atom:link rel="self"> if it exists
        atom_link = channel.find('atom:link[@rel="self"]', namespaces=NAMESPACES)
        if atom_link is not None:
            atom_link.set('href', f"{url_root}/api/modified_rss/{encoded_rss_url}")

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
            link_elem.text = f"{url_root}/api/modified_rss/{encoded_rss_url}"

        # Update or add a new <itunes:new-feed-url> element
        new_feed_url = channel.find('itunes:new-feed-url', namespaces=NAMESPACES)
        if new_feed_url is None:
            new_feed_url = ET.SubElement(channel, f"{{{NAMESPACES['itunes']}}}new-feed-url")
        new_feed_url.text = f"{url_root}/api/modified_rss/{encoded_rss_url}"

        # Update the <atom:link> element
        atom_link = channel.find('atom:link[@rel="self"]', namespaces=NAMESPACES)
        if atom_link is not None:
            atom_link.set('href', f"{url_root}/api/modified_rss/{encoded_rss_url}")
        else:
            atom_link = ET.SubElement(channel, f"{{{NAMESPACES['atom']}}}link", attrib={
                'href': f"{url_root}/api/modified_rss/{encoded_rss_url}",
                'rel': 'self',
                'type': 'application/rss+xml'
            })

        enable_date = get_auto_process_enable_date(original_rss_url)
        logging.info(f"Auto-processing enabled date for {original_rss_url}: {enable_date}")

        # Process items
        episodes_to_process = []
        items_to_remove = []
        for item in channel.findall('item'):
            item_title = item.find('title')
            if item_title is not None:
                episode_title = item_title.text
                pub_date = item.find('pubDate')
                if pub_date is not None:
                    try:
                        episode_published_date = datetime.strptime(pub_date.text, "%a, %d %b %Y %H:%M:%S %z")
                    except ValueError:
                        logging.warning(f"Could not parse pubDate for episode: {episode_title}. Using current time.")
                        episode_published_date = datetime.now(timezone.utc)
                else:
                    episode_published_date = datetime.now(timezone.utc)

                logging.info(f"Checking episode: {episode_title}, Published: {episode_published_date}")

                processed_episode = next(
                    (ep for ep in processed_podcasts.get(original_rss_url, [])
                     if ep.get('episode_title') == episode_title),
                    None
                )

                if processed_episode and processed_episode.get('status') == 'completed':
                    logging.info(f"Episode already processed: {episode_title}")
                    update_processed_item(item, processed_episode, namespaces)
                elif is_episode_being_processed(original_rss_url, episode_title):
                    logging.info(f"Episode currently being processed: {episode_title}")
                    items_to_remove.append(item)
                elif enable_date and is_episode_new(original_rss_url, episode_published_date):
                    logging.info(f"New episode detected for processing: {episode_title}, Published: {episode_published_date}")
                    episodes_to_process.append((episode_title, episode_published_date))
                    items_to_remove.append(item)
                else:
                    logging.info(f"Episode not new or already processed: {episode_title}, Published: {episode_published_date}")
                    break  # Stop processing further episodes

        # Remove items outside the loop to avoid modifying the list while iterating
        for item in items_to_remove:
            channel.remove(item)

        if episodes_to_process:
            logging.info(f"Found {len(episodes_to_process)} new episodes to process: {[ep[0] for ep in episodes_to_process]}")
            process_new_episodes(original_rss_url, episodes_to_process)
        else:
            logging.info("No new episodes found for processing")

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

def update_processed_item(item, processed_episode, namespaces):
    # Update the enclosure URL to the Firebase Storage URL
    enclosure = item.find('enclosure')
    if enclosure is not None and processed_episode.get('edited_url'):
        enclosure.set('url', processed_episode['edited_url'])

    # Add "(Optimized)" to the title
    item_title = item.find('title')
    if item_title is not None:
        item_title.text = f"{item_title.text} (Optimized)"

    # Update other elements for processed episodes
    guid = item.find('guid')
    if guid is not None:
        guid.text = f"{guid.text}_optimized"

    pub_date = item.find('pubDate')
    if pub_date is not None:
        pub_date.text = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())

    itunes_title = item.find('itunes:title', namespaces=namespaces)
    if itunes_title is not None:
        itunes_title.text = f"{itunes_title.text} (Optimized)"

    # Update the duration if available
    duration_elem = item.find('itunes:duration', namespaces=namespaces)
    if duration_elem is not None and 'duration' in processed_episode:
        duration_elem.text = format_duration(processed_episode['duration'])

def process_new_episodes(rss_url, episodes_to_process):
    logging.info(f"Processing new episodes for {rss_url}")
    episodes = get_podcast_episodes(rss_url)
    for episode_title, _ in episodes_to_process:
        episode_index = next((i for i, ep in enumerate(episodes) if ep['title'] == episode_title), None)
        if episode_index is not None:
            job_id = str(uuid.uuid4())
            process_podcast_task.delay(rss_url, episode_index, job_id)
            logging.info(f"Initiated processing for new episode: {episode_title} with job_id: {job_id}")
        else:
            logging.error(f"Could not find episode {episode_title} in the feed")

def get_modified_rss_feed(rss_url, processed_podcasts):
    logging.info(f"Generating modified RSS feed for {rss_url}")

    rss_specific_podcasts = processed_podcasts.get(rss_url, [])
    logging.info(f"Found {len(rss_specific_podcasts)} processed episodes for {rss_url}")

    return create_modified_rss_feed(rss_url, {rss_url: rss_specific_podcasts})
