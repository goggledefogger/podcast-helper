import os
import sys

# Add the backend directory to the Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Increase task time limit (e.g., 2 hours)
task_time_limit = 7200

# Limit concurrency to reduce memory usage
worker_concurrency = 2

# Add these lines to improve task execution
worker_prefetch_multiplier = 1
worker_max_tasks_per_child = 1

# **Change the worker pool from 'prefork' to 'threads'**
worker_pool = 'threads'
# Remove or comment out the prefork-specific settings
# worker_pool_restarts = True
