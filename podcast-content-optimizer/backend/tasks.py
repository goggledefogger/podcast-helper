from celery import Celery
from podcast_processor import process_podcast_episode
import logging

app = Celery('tasks', broker='redis://localhost:6379/0')

@app.task(bind=True, name='process_podcast_task', acks_late=True)
def process_podcast_task(self, rss_url, episode_index, job_id):
    # Generate a unique task ID
    unique_id = f"{rss_url}:{episode_index}"

    # Check if a task with this ID is already running
    if app.AsyncResult(unique_id).state in ['PENDING', 'STARTED', 'RETRY']:
        logging.info(f"Task for {unique_id} is already running. Skipping.")
        return

    # Set the task ID
    self.request.id = unique_id

    process_podcast_episode(rss_url, episode_index, job_id)
