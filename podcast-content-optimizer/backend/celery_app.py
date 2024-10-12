from celery import Celery
import os
import sys

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Set the default Flask app
os.environ.setdefault('FLASK_APP', 'api.app')

app = Celery('podcast_content_optimizer')

# Load configuration from a configuration object
app.config_from_object('celeryconfig')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks(['api'])

if __name__ == '__main__':
    app.start()
