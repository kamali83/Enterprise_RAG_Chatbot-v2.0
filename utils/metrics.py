from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter("request_count", "Total API Requests")
ERROR_COUNT = Counter("error_count", "Total API Errors")
REQUEST_LATENCY = Histogram("request_latency_seconds", "Request latency")