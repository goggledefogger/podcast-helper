import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_set(key, value, expiration=3600):
    redis_client.setex(key, expiration, json.dumps(value))

def cache_get(key):
    value = redis_client.get(key)
    if value:
        return json.loads(value)
    return None
