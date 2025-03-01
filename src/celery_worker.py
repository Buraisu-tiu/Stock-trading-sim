from celery import Celery
import os

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("tasks", broker=redis_url, backend=redis_url)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)

@celery.task
def example_task(x, y):
    return x + y
