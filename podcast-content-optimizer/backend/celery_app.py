from celery import Celery
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
logger.info(f"Added {current_dir} to Python path")

# Set the default Flask app
os.environ.setdefault('FLASK_APP', 'api.app')
logger.info("Set FLASK_APP environment variable")

app = Celery('podcast_content_optimizer')
logger.info("Created Celery app")

# Load configuration from a configuration object
app.config_from_object('celeryconfig')
logger.info("Loaded Celery configuration")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks(['api'])
logger.info("Auto-discovered tasks")

# Import tasks explicitly
try:
    from api import tasks
    logger.info("Successfully imported tasks from api")
except ImportError as e:
    logger.error(f"Failed to import tasks from api: {str(e)}")

if __name__ == '__main__':
    logger.info("Starting Celery app")
    app.start()
