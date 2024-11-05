import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin, quote
import time
import logging
import traceback
import requests
import os
from mutagen.mp3 import MP3
from utils import format_duration, is_episode_processed, is_episode_being_processed, get_podcast_episodes, is_episode_new, get_auto_process_enable_date, get_db, safe_filename, load_processed_podcasts
from flask import request
from io import StringIO
from utils import safe_filename
import urllib.parse
from firebase_admin import storage
import json
from podcast_processor import process_podcast_episode
from tasks import process_podcast_task
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
        # Check if podcast is in auto-processed list
        processed_data = load_processed_podcasts()
        auto_processed = processed_data.get('auto_processed_podcasts', [])
        if not any(p['rss_url'] == original_rss_url for p in auto_processed):
            logging.info(f"RSS URL {original_rss_url} is not in auto-processed list, skipping feed creation")
            return None

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

        enable_date = get_auto_process_enable_date(original_rss_url)
        logging.info(f"Auto-processing enabled date for {original_rss_url}: {enable_date}")

        # Build mappings from episode identifiers to items
        guid_to_item = {}
        title_to_item = {}
        for item in channel.findall('item'):
            # Get the GUID
            guid_elem = item.find('guid')
            if guid_elem is not None and guid_elem.text:
                episode_guid = guid_elem.text.strip()
                guid_to_item[episode_guid] = item
            else:
                episode_guid = None

            # Get the title
            item_title_elem = item.find('title')
            if item_title_elem is not None and item_title_elem.text:
                episode_title = item_title_elem.text.strip()
                title_to_item[episode_title] = item
            else:
                logging.warning("Item without a title found in RSS feed.")
                continue  # Skip items without a title

        # Get the list of processed episodes for the current RSS URL
        processed_episodes_list = processed_podcasts.get(original_rss_url, [])

        # Create sets of processed episode titles and GUIDs for quick lookup
        processed_episode_titles = set()
        processed_episode_guids = set()
        for pe in processed_episodes_list:
            if pe.get('status') == 'completed':
                if 'episode_title' in pe and pe['episode_title']:
                    processed_episode_titles.add(pe['episode_title'].strip())
                if 'episode_guid' in pe and pe['episode_guid']:
                    processed_episode_guids.add(pe['episode_guid'].strip())

        # Sort items in reverse chronological order
        items = channel.findall('item')
        def parse_pub_date(pub_date_str):
            try:
                return datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError:
                try:
                    dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S")
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    logging.warning(f"Could not parse pubDate: {pub_date_str}. Using current time.")
                    return datetime.now(timezone.utc)

        items_sorted = sorted(items, key=lambda x: parse_pub_date(x.find('pubDate').text if x.find('pubDate') is not None else ''), reverse=True)

        episodes_to_process = []
        items_to_remove = []

        for item in items_sorted:
            # Get the GUID
            guid_elem = item.find('guid')
            episode_guid = guid_elem.text.strip() if (guid_elem is not None and guid_elem.text) else None

            # Get the title
            item_title_elem = item.find('title')
            episode_title = item_title_elem.text.strip() if (item_title_elem is not None and item_title_elem.text) else None

            if not episode_title:
                logging.warning("Item without a title found in RSS feed.")
                continue  # Skip items without a title

            # Get publication date
            pub_date_elem = item.find('pubDate')
            episode_published_date = parse_pub_date(pub_date_elem.text) if (pub_date_elem is not None and pub_date_elem.text) else datetime.now(timezone.utc)

            # Check if episode is older than enabled date
            is_older_than_enabled_date = enable_date and episode_published_date < enable_date
            if is_older_than_enabled_date:
                logging.info(f"Episode older than enable date: {episode_title}")
                # Keep episodes older than enable date in the feed without modification
                continue

            # Check if the episode is already processed
            is_already_processed = False
            is_deleted = False
            for processed_episode in processed_episodes_list:
                if ((episode_guid and processed_episode.get('episode_guid') == episode_guid) or
                    (episode_title and processed_episode.get('episode_title') == episode_title)):
                    is_already_processed = True
                    is_deleted = processed_episode.get('status') == 'deleted'
                    break

            # Remove episode from feed if it's:
            # 1. Currently being processed OR
            # 2. Not processed yet and newer than enable date
            if is_episode_being_processed(original_rss_url, episode_title) or (not is_already_processed and not is_older_than_enabled_date):
                logging.info(f"Removing episode from feed: {episode_title} (Being processed: {is_episode_being_processed(original_rss_url, episode_title)})")
                items_to_remove.append(item)
                if not is_already_processed:
                    episodes_to_process.append((episode_title, episode_published_date))
                continue

            # Don't remove deleted episodes from the feed
            if is_already_processed and is_deleted:
                continue

            # Only add to processing queue if not already processed
            if not is_already_processed:
                logging.info(f"New episode detected for processing: {episode_title}, Published: {episode_published_date}")
                episodes_to_process.append((episode_title, episode_published_date))
                items_to_remove.append(item)

        # Remove items that are being processed
        for item in items_to_remove:
            channel.remove(item)

        # Process new episodes if any
        if episodes_to_process:
            logging.info(f"Found {len(episodes_to_process)} new episodes to process.")
            process_new_episodes(original_rss_url, episodes_to_process)
        else:
            logging.info("No new episodes found for processing")

        # Add back all processed episodes (including deleted ones)
        for processed_episode in processed_episodes_list:
            if processed_episode.get('status') in ['completed', 'deleted']:
                episode_title = processed_episode.get('episode_title', '').strip()
                episode_guid = processed_episode.get('episode_guid', '').strip()

                # Find the original item
                item = None
                if episode_guid and episode_guid in guid_to_item:
                    item = guid_to_item[episode_guid]
                    logging.info(f"Found item by GUID for episode: {episode_title}")
                elif episode_title and episode_title in title_to_item:
                    item = title_to_item[episode_title]
                    logging.info(f"Found item by Title for episode: {episode_title}")

                if item is not None:
                    logging.info(f"Updating processed episode: {episode_title} (Status: {processed_episode.get('status')})")
                    update_processed_item(item, processed_episode, NAMESPACES)
                    channel.append(item)
                else:
                    logging.warning(f"Could not find original item for processed episode: {episode_title}")

        # Perform modifications on the channel and items
        # Update <itunes:new-feed-url> if it exists
        new_feed_url = channel.find('itunes:new-feed-url', namespaces=NAMESPACES)
        if new_feed_url is not None:
            new_feed_url.text = f"{url_root}/api/modified_rss/{encoded_rss_url}"

        # Update <atom:link rel="self"> if it exists
        atom_link = channel.find('atom:link[@rel="self"]', namespaces=NAMESPACES)
        if atom_link is not None:
            atom_link.set('href', f"{url_root}/api/modified_rss/{encoded_rss_url}")
        else:
            atom_link = ET.SubElement(channel, f"{{{NAMESPACES['atom']}}}link", attrib={
                'href': f"{url_root}/api/modified_rss/{encoded_rss_url}",
                'rel': 'self',
                'type': 'application/rss+xml'
            })

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
    logging.info(f"Updating episode: {processed_episode.get('episode_title')}")

    # Update the enclosure URL
    enclosure = item.find('enclosure')
    if enclosure is not None:
        if processed_episode.get('status') == 'deleted':
            # Remove the 'url' attribute since the file is deleted
            if 'url' in enclosure.attrib:
                del enclosure.attrib['url']
                logging.info(f"Removed enclosure URL for deleted episode: {processed_episode.get('episode_title')}")
        else:
            edited_url = processed_episode.get('edited_url')
            if edited_url:
                old_url = enclosure.get('url')
                enclosure.set('url', edited_url)
                logging.info(f"Updated enclosure URL from {old_url} to {edited_url}")
            else:
                logging.warning(f"No 'edited_url' for episode: {processed_episode.get('episode_title')}")
    else:
        logging.warning("No enclosure element found in item.")

    # Update the title
    item_title = item.find('title')
    if item_title is not None:
        old_title = item_title.text
        if processed_episode.get('status') == 'deleted':
            item_title.text = f"{item_title.text} (Opt / Deleted)"
        else:
            item_title.text = f"{item_title.text} (Optimized)"
        logging.info(f"Updated title from '{old_title}' to '{item_title.text}'")
    else:
        logging.warning("No title element found in item.")

    # Update other elements for processed episodes
    guid = item.find('guid')
    if guid is not None:
        old_guid = guid.text
        guid.text = f"{guid.text}_optimized"
        logging.info(f"Updated GUID from {old_guid} to {guid.text}")
    else:
        logging.warning("No GUID element found in item.")

    pub_date = item.find('pubDate')
    if pub_date is not None:
        old_pub_date = pub_date.text
        new_pub_date = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
        pub_date.text = new_pub_date
        logging.info(f"Updated pubDate from {old_pub_date} to {new_pub_date}")
    else:
        logging.warning("No pubDate element found in item.")

    itunes_title = item.find('itunes:title', namespaces=namespaces)
    if itunes_title is not None:
        old_itunes_title = itunes_title.text
        itunes_title.text = f"{itunes_title.text} (Optimized)"
        logging.info(f"Updated iTunes title from '{old_itunes_title}' to '{itunes_title.text}'")
    else:
        logging.warning("No itunes:title element found in item.")

    # Update the duration if available
    duration_elem = item.find('itunes:duration', namespaces=namespaces)
    if duration_elem is not None:
        if 'duration' in processed_episode:
            old_duration = duration_elem.text
            duration_elem.text = format_duration(processed_episode['duration'])
            logging.info(f"Updated duration from {old_duration} to {duration_elem.text}")
        else:
            logging.warning(f"No 'duration' in processed_episode for {processed_episode.get('episode_title')}")
    else:
        logging.warning("No itunes:duration element found in item.")

    # Additional modifications for deleted episodes
    if processed_episode.get('status') == 'deleted':
        # Remove the 'enclosure' element entirely if desired
        if enclosure is not None:
            item.remove(enclosure)
            logging.info(f"Removed enclosure element for deleted episode: {processed_episode.get('episode_title')}")

        # Optionally, update the description to indicate deletion
        description_elem = item.find('description')
        if description_elem is not None:
            description_elem.text = f"This episode has been deleted."
            logging.info(f"Updated description for deleted episode: {processed_episode.get('episode_title')}")


def process_new_episodes(rss_url, episodes_to_process):
    logging.info(f"Processing new episodes for {rss_url}")
    episodes = get_podcast_episodes(rss_url)
    db = get_db()

    for episode_title, _ in episodes_to_process:
        episode_index = next((i for i, ep in enumerate(episodes) if ep['title'] == episode_title), None)
        if episode_index is not None:
            job_key = f"job:{rss_url}:{episode_title}"
            lock_key = f"lock:{job_key}"

            # Try to acquire a lock
            lock_acquired = db.setnx(lock_key, 'locked')
            if lock_acquired:
                try:
                    # Set an expiration on the lock
                    db.expire(lock_key, 3600)  # 1 hour expiration

                    job_id = str(uuid.uuid4())
                    process_podcast_task.delay(rss_url, episode_index, job_id)
                    logging.info(f"Initiated processing for new episode: {episode_title} with job_id: {job_id}")
                finally:
                    # Release the lock
                    db.delete(lock_key)
            else:
                logging.info(f"Processing already in progress for episode: {episode_title}. Skipping.")
        else:
            logging.error(f"Could not find episode {episode_title} in the feed")

def get_modified_rss_feed(rss_url, processed_podcasts):
    logging.info(f"Generating modified RSS feed for {rss_url}")

    rss_specific_podcasts = processed_podcasts.get(rss_url, [])
    logging.info(f"Found {len(rss_specific_podcasts)} processed episodes for {rss_url}")

    return create_modified_rss_feed(rss_url, {rss_url: rss_specific_podcasts})
