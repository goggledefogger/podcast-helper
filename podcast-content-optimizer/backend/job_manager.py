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
    redis_client.setex(f"job_status:{job_id}", 3600, json.dumps(job_status))

def get_job_status(job_id):
    status = redis_client.get(f"job_status:{job_id}")
    return json.loads(status) if status else None

def append_job_log(job_id, log_entry):
    key = f"job_log:{job_id}"
    redis_client.rpush(key, json.dumps(log_entry))
    redis_client.expire(key, 3600)  # Set expiration to 1 hour

def get_job_logs(job_id):
    key = f"job_log:{job_id}"
    logs = redis_client.lrange(key, 0, -1)
    return [json.loads(log) for log in logs]

def update_job_info(job_id, job_info):
    key = f"job_info:{job_id}"
    redis_client.hmset(key, job_info)
    redis_client.expire(key, 3600)  # Set expiration to 1 hour
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

def delete_job(job_id):
    redis_client.delete(f"job_status:{job_id}")
    redis_client.delete(f"job_log:{job_id}")
