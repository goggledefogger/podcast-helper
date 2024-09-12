import feedparser
import logging
import traceback

def get_podcast_episodes(rss_url):
    try:
        logging.info(f"Parsing RSS feed: {rss_url}")
        feed = feedparser.parse(rss_url)

        if feed.bozo:
            logging.error(f"Error parsing RSS feed: {feed.bozo_exception}")
            raise ValueError(f"Invalid RSS feed: {feed.bozo_exception}")

        if not feed.entries:
            logging.warning(f"No entries found in the RSS feed: {rss_url}")
            return []

        episodes = []
        for i, entry in enumerate(feed.entries):
            episode = {
                'number': i + 1,
                'title': entry.get('title', 'Untitled'),
                'published': entry.get('published', 'Unknown date')
            }
            episodes.append(episode)

        logging.info(f"Successfully parsed {len(episodes)} episodes")
        return episodes
    except Exception as e:
        logging.error(f"Error in get_podcast_episodes: {str(e)}")
        logging.error(traceback.format_exc())
        raise ValueError(f"Failed to parse podcast episodes: {str(e)}")

def download_episode(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 KB

    with open(filename, 'wb') as file, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(block_size):
            size = file.write(data)
            progress_bar.update(size)
