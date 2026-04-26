import os

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'mongodb://mongo:27017/')
task_track_started = True
task_acks_late = True
worker_prefetch_multiplier = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
task_default_retry_delay = int(os.getenv("CELERY_TASK_DEFAULT_RETRY_DELAY", "5"))
