from celery_app import app
from podcast_processor import process_podcast_episode
import logging
import traceback

@app.task(bind=True, name='api.tasks.process_podcast_task')
def process_podcast_task(self, rss_url, episode_index, job_id):
    logging.info(f"Starting process_podcast_task for job_id: {job_id}")
    try:
        from api.routes import update_job_status, save_processed_podcast
    except ImportError:
        logging.error("Failed to import update_job_status and save_processed_podcast")
        return {"error": "Internal server error"}

    try:
        update_job_status(job_id, 'in_progress', 'Initializing')

        result = process_podcast_episode(rss_url, episode_index)

        save_processed_podcast(result)
        update_job_status(job_id, 'completed', 'Completed')

        return result
    except Exception as e:
        logging.error(f"Error in podcast processing for job_id {job_id}: {str(e)}")
        logging.error(traceback.format_exc())
        update_job_status(job_id, 'failed', 'Failed', error=str(e))
        return {"error": str(e)}
