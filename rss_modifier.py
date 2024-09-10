import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import time
import logging
from functools import lru_cache

# Cache to store modified RSS feeds
rss_cache = {}

def create_modified_rss_feed(original_rss_url, processed_podcasts, url_root):
    # Check if the cached RSS feed is still valid
    cached_rss = rss_cache.get(original_rss_url)
    if cached_rss and time.time() - cached_rss['timestamp'] < 3600:  # 1 hour cache
        return cached_rss['content']

    # If not in cache or expired, create a new modified RSS feed
    feed = feedparser.parse(original_rss_url)

    # Create a new RSS feed
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    # Add channel information
    ET.SubElement(channel, "title").text = feed.feed.title
    ET.SubElement(channel, "link").text = feed.feed.link
    ET.SubElement(channel, "description").text = feed.feed.description

    # Create a dictionary of processed episodes for quick lookup
    processed_episodes = {ep['rss_url']: ep for ep in processed_podcasts}

    # Add items (episodes)
    for entry in feed.entries:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = entry.title
        ET.SubElement(item, "link").text = entry.link
        ET.SubElement(item, "description").text = entry.description
        ET.SubElement(item, "pubDate").text = entry.published

        for link in entry.links:
            if link.type == 'audio/mpeg':
                enclosure = ET.SubElement(item, "enclosure")

                # Check if this specific episode has been processed
                processed_episode = next((ep for ep in processed_podcasts if ep['rss_url'] == original_rss_url and ep['edited_url'].split('/')[-1].startswith(entry.title.replace(' ', '_'))), None)

                if processed_episode:
                    # Use the edited audio URL for the processed episode
                    edited_url = urljoin(url_root, processed_episode['edited_url'])
                    enclosure.set("url", edited_url)
                else:
                    # Use the original URL for unprocessed episodes
                    enclosure.set("url", link.href)

                enclosure.set("type", "audio/mpeg")
                break

    # Convert the XML tree to a string
    modified_rss = ET.tostring(rss, encoding="unicode")

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
