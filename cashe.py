import redis
import hashlib
import json

r = redis.Redis(host='localhost', port=6379, db=0)

def get_cache_key(query):
    return hashlib.md5(query.encode()).hexdigest()

def get_cached_response(query):
    key = get_cache_key(query)
    result = r.get(key)
    return json.loads(result) if result else None

def set_cached_response(query, response):
    key = get_cache_key(query)
    r.set(key, json.dumps(response), ex=3600)