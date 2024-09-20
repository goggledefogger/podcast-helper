from celery_app import app
from podcast_processor import process_podcast_episode
from job_manager import update_job_status, append_job_log
import logging
import traceback

@app.task(bind=True, name='api.tasks.process_podcast_task')
def process_podcast_task(self, rss_url, episode_index, job_id):
    logging.info(f"Starting process_podcast_task for job_id: {job_id}")
    try:
        update_job_status(job_id, 'in_progress', 'INITIALIZATION', 0, 'Starting podcast processing')
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
