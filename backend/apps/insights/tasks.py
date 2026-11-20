from typing import Any, Optional
from celery import shared_task

from .services import execute_ai_pipeline


@shared_task(name="apps.insights.tasks.run_ai_pipeline_task")
def run_ai_pipeline_task(
    config: Optional[dict[str, Any]] = None,
    product_id: Optional[int] = None,
) -> dict[str, Any]:
    return execute_ai_pipeline(config=config, product_id=product_id)
