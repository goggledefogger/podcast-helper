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

# Define common namespace prefixes
NAMESPACES = {
    'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'atom': 'http://www.w3.org/2005/Atom',
    'media': 'http://search.yahoo.com/mrss/',
}

def get_episode_folder(podcast_title, episode_title):
    safe_podcast_title = "".join([c for c in podcast_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    safe_episode_title = "".join([c for c in episode_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    return os.path.join('output', safe_podcast_title, safe_episode_title)

def get_audio_info(file_path):
    file_size = os.path.getsize(file_path)
    audio = MP3(file_path)
    duration = int(audio.info.length)
    return file_size, duration

def download_image(image_url, podcast_title):
    safe_podcast_title = "".join([c for c in podcast_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    image_dir = os.path.join('output', safe_podcast_title, 'images')
    os.makedirs(image_dir, exist_ok=True)

    # Include podcast title in the image filename
    image_filename = f"podcast_image.jpg"
    image_path = os.path.join(image_dir, image_filename)

    if not os.path.exists(image_path):
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            with open(image_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Successfully downloaded image for {podcast_title} to {image_path}")
        except requests.RequestException as e:
            logging.error(f"Failed to download image for {podcast_title}: {str(e)}")
            return None
    else:
        logging.info(f"Image already exists for {podcast_title} at {image_path}")

    return f"/output/{safe_podcast_title}/images/{image_filename}"

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
    ET.register_namespace('', 'http://www.w3.org/2005/Atom')
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)

    root = ET.fromstring(response.content)

    # Find the channel element
    channel = root.find('channel')
    if channel is not None:
        # Look for the image element, considering potential namespaces
        image_elem = None
        for elem in channel:
            if elem.tag.endswith('image'):
                image_elem = elem
                break

        if image_elem is None:
            # Try to find itunes:image
            image_elem = channel.find('itunes:image', namespaces=NAMESPACES)

        if image_elem is not None:
            logging.info(f"Found image element: {ET.tostring(image_elem, encoding='unicode')}")
            # Find the URL of the image
            image_url = None
            if 'href' in image_elem.attrib:
                image_url = image_elem.get('href')
            elif image_elem.find('url') is not None:
                image_url = image_elem.find('url').text

            if image_url:
                logging.info(f"Found original image URL: {image_url}")
                podcast_title = root.find('.//title').text
                # Download and get the local path of the image
                local_image_path = download_image(image_url, podcast_title)
                if local_image_path:
                    # Update the image URL in the RSS feed
                    new_image_url = urljoin(url_root, local_image_path.lstrip('/'))
                    if 'href' in image_elem.attrib:
                        image_elem.set('href', new_image_url)
                    else:
                        url_elem = image_elem.find('url')
                        if url_elem is not None:
                            url_elem.text = new_image_url
                        else:
                            ET.SubElement(image_elem, 'url').text = new_image_url
                    logging.info(f"Updated image URL to {new_image_url}")
                else:
                    logging.warning("Failed to download image, keeping original URL")
            else:
                logging.warning("Image URL not found in the image element")
        else:
            logging.warning("Image element not found in RSS feed")
    else:
        logging.warning("Channel element not found in RSS feed")

    # Create a dictionary of processed episodes for quick lookup
    processed_episodes = {ep['rss_url']: ep for ep in processed_podcasts}

    # Find all enclosure elements in the RSS feed
    for item in root.findall('.//item'):
        enclosure = item.find('enclosure')
        if enclosure is not None:
            original_url = enclosure.get('url')
            episode_title = item.find('title').text

            # Check if this specific episode has been processed
            processed_episode = next((ep for ep in processed_podcasts if ep['rss_url'] == original_rss_url and ep['episode_title'] == episode_title), None)

            if processed_episode:
                # Construct the correct path including the podcast title
                podcast_title = processed_episode['podcast_title']
                safe_podcast_title = "".join([c for c in podcast_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                safe_episode_title = "".join([c for c in episode_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                relative_path = f"output/{safe_podcast_title}/{safe_episode_title}/{os.path.basename(processed_episode['edited_url'])}"

                # Use the edited audio URL for the processed episode
                edited_url = urljoin(url_root, relative_path)
                enclosure.set("url", edited_url)

                # Update the file size and duration
                edited_file_path = os.path.join('output', relative_path)
                if os.path.exists(edited_file_path):
                    new_size, new_duration = get_audio_info(edited_file_path)

                    # Update the length attribute in the enclosure element
                    enclosure.set("length", str(new_size))

                    # Update the duration element
                    duration_elem = item.find('itunes:duration', namespaces=NAMESPACES)
                    if duration_elem is not None:
                        duration_elem.text = str(new_duration)
                else:
                    logging.warning(f"Edited file not found: {edited_file_path}")

    # Convert the modified XML tree back to a string
    ET.register_namespace('', '')  # Unset the default namespace
    modified_rss = ET.tostring(root, encoding="unicode", xml_declaration=True)

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
