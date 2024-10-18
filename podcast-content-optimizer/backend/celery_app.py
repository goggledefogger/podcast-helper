from celery import Celery
import os
import sys

# Add the current directory and its parent to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.extend([current_dir, parent_dir])

# Set the default Flask app
os.environ.setdefault('FLASK_APP', 'api.app')

# Initialize Celery
app = Celery('podcast_content_optimizer')

# Load configuration from celeryconfig.py
app.config_from_object('celeryconfig')

# Auto-discover tasks in the 'tasks.py' file
app.autodiscover_tasks(['tasks'])

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(10.0, test_task.s(), name='add every 10')

@app.task
def test_task():
    print("Test task running")

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

if __name__ == '__main__':
    app.start()
