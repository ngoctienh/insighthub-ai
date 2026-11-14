from celery import shared_task

from .services import execute_ai_pipeline


@shared_task(name="apps.insights.tasks.run_ai_pipeline_task")
def run_ai_pipeline_task(job_id: int) -> dict:
    job = execute_ai_pipeline(job_id)
    return {"job_id": job.id, "status": job.status, "metrics": job.metrics}
