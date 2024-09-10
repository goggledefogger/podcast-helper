import feedparser
import xml.etree.ElementTree as ET

def create_modified_rss_feed(original_rss_url):
    # Parse the original RSS feed
    feed = feedparser.parse(original_rss_url)

    # Create a new RSS feed
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    # Add channel information
    ET.SubElement(channel, "title").text = feed.feed.title
    ET.SubElement(channel, "link").text = feed.feed.link
    ET.SubElement(channel, "description").text = feed.feed.description

    # Add items (episodes)
    for entry in feed.entries:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = entry.title
        ET.SubElement(item, "link").text = entry.link
        ET.SubElement(item, "description").text = entry.description
        ET.SubElement(item, "pubDate").text = entry.published

        # Replace the audio file URL with the edited version
        for link in entry.links:
            if link.type == 'audio/mpeg':
                enclosure = ET.SubElement(item, "enclosure")
                # Here, you would typically look up the edited URL from your database
                edited_url = f"/output/{entry.title.replace(' ', '_')}_edited.mp3"
                enclosure.set("url", edited_url)
                enclosure.set("type", "audio/mpeg")
                break

    # Convert the XML tree to a string
    return ET.tostring(rss, encoding="unicode")
