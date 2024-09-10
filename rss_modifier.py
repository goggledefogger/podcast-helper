import feedparser
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin

def create_modified_rss_feed(original_rss_url, processed_podcasts, url_root):
    # Parse the original RSS feed
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
    return ET.tostring(rss, encoding="unicode")
