import os
import logging
import traceback
from dotenv import load_dotenv
from podcast_processor import process_podcast_episode
from utils import get_podcast_episodes, choose_episode

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

if __name__ == "__main__":
    try:
        # Get podcast RSS feed URL from user
        rss_url = input("Enter the podcast RSS feed URL: ")

        # Get available episodes
        episodes = get_podcast_episodes(rss_url)

        # Let user choose an episode
        chosen_episode = choose_episode(episodes)

        # Process the chosen episode
        result = process_podcast_episode(rss_url, episodes.index(chosen_episode))
        logging.info(f"Processed episode: {chosen_episode['title']}")
        logging.info(f"Edited audio: {result['edited_url']}")
        logging.info(f"Transcript: {result['transcript_file']}")
        logging.info(f"Unwanted content: {result['unwanted_content_file']}")

    except Exception as e:
        logging.error(f"Error processing episode: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")

    finally:
        logging.info("Script completed")
