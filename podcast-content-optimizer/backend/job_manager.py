import redis
import json
import time
import logging

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def update_job_status(job_id, status, current_stage, progress, message):
    job_status = {
        'status': status,
        'current_stage': current_stage,
        'progress': progress,
        'message': message,
        'timestamp': time.time()
    }
    redis_client.set(f"job_status:{job_id}", json.dumps(job_status))

def get_job_status(job_id):
    status = redis_client.get(f"job_status:{job_id}")
    return json.loads(status) if status else None

def append_job_log(job_id, log_entry):
    key = f"job_log:{job_id}"
    redis_client.rpush(key, json.dumps(log_entry))

def get_job_logs(job_id):
    key = f"job_log:{job_id}"
    logs = redis_client.lrange(key, 0, -1)
    return [json.loads(log) for log in logs]

def update_job_info(job_id, job_info):
    key = f"job_info:{job_id}"
    if 'rss_url' not in job_info:
        logging.warning(f"rss_url not provided for job_id: {job_id}")
    redis_client.hmset(key, job_info)
    logging.info(f"Updated job info for job_id: {job_id}, info: {job_info}")

def get_job_info(job_id):
    key = f"job_info:{job_id}"
    info = redis_client.hgetall(key)
    if info:
        return {k.decode('utf-8'): v.decode('utf-8') for k, v in info.items()}
    return None

def get_current_jobs():
    jobs = []
    for key in redis_client.scan_iter("job_status:*"):
        job_id = key.decode('utf-8').split(':')[1]
        status = get_job_status(job_id)
        job_info = get_job_info(job_id)
        if status and status['status'] in ['queued', 'in_progress']:
            job = {'job_id': job_id, 'status': status}
            if job_info:
                job.update(job_info)
            jobs.append(job)
    logging.info(f"Current jobs: {jobs}")
    return jobs

def mark_job_completed(job_id):
    update_job_status(job_id, 'completed', 'COMPLETION', 100, 'Podcast processing completed')
    # We're not deleting the job data immediately after completion
    # This allows the frontend to fetch the final status
    logging.info(f"Marked job {job_id} as completed")

def mark_job_failed(job_id, error_message):
    update_job_status(job_id, 'failed', 'ERROR', 0, f'Error: {error_message}')
    # We're not deleting the job data immediately after failure
    # This allows the frontend to fetch the error status
    logging.info(f"Marked job {job_id} as failed")

def delete_job_data(job_id):
    redis_client.delete(f"job_status:{job_id}")
    redis_client.delete(f"job_log:{job_id}")
    redis_client.delete(f"job_info:{job_id}")
    logging.info(f"Deleted all Redis keys for job {job_id}")

def delete_job(job_id):
    # Perform any additional cleanup if needed
    # For now, it just calls delete_job_data
    delete_job_data(job_id)
    logging.info(f"Deleted job {job_id}")
