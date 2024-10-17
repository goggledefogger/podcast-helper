from celery import shared_task
from podcast_processor import process_podcast_episode
import logging
from utils import initialize_firebase

@shared_task(name='process_podcast_task')
def process_podcast_task(rss_url, episode_index, job_id):
    logging.info(f"Starting podcast processing task for {rss_url}, episode {episode_index}, job {job_id}")
    try:
        # Initialize Firebase within the task
        initialize_firebase()

        result = process_podcast_episode(rss_url, episode_index, job_id)
        logging.info(f"Podcast processing task completed for {rss_url}, episode {episode_index}, job {job_id}")
        return result
    except Exception as e:
        logging.error(f"Error in podcast processing task: {str(e)}")
        raise
