from celery_app import app
from podcast_processor import process_podcast_episode
from job_manager import update_job_status, append_job_log, update_job_info
from utils import get_podcast_episodes  # Add this import
import logging
import traceback

@app.task(bind=True, name='api.tasks.process_podcast_task')
def process_podcast_task(self, rss_url, episode_index, job_id):
    logging.info(f"Starting process_podcast_task for job_id: {job_id}, rss_url: {rss_url}, episode_index: {episode_index}")
    try:
        # Fetch episode information
        episodes = get_podcast_episodes(rss_url)
        if not episodes:
            raise ValueError("No episodes found in the RSS feed")
        if episode_index >= len(episodes):
            raise ValueError("Episode index out of range")
        episode = episodes[episode_index]

        # Update job info with RSS URL and episode title
        job_info = {
            'rss_url': rss_url,
            'episode_title': episode['title'],
            'podcast_name': episode['podcast_title']
        }
        update_job_info(job_id, job_info)

        logging.info(f"Updated job info for job_id: {job_id}, info: {job_info}")

        update_job_status(job_id, 'in_progress', 'INITIALIZATION', 5, 'Job started')
        append_job_log(job_id, {'stage': 'INITIALIZATION', 'message': 'Task started'})

        result = process_podcast_episode(rss_url, episode_index, job_id)

        update_job_status(job_id, 'completed', 'COMPLETION', 100, 'Podcast processing completed')
        append_job_log(job_id, {'stage': 'COMPLETION', 'message': 'Task completed successfully'})

        return result
    except Exception as e:
        logging.error(f"Error in podcast processing for job_id {job_id}: {str(e)}")
        logging.error(traceback.format_exc())
        update_job_status(job_id, 'failed', 'FAILED', 0, f'Error: {str(e)}')
        append_job_log(job_id, {'stage': 'FAILED', 'message': f'Task failed: {str(e)}'})
        return {"error": str(e)}
