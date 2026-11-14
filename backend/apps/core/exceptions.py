import logging
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict) and "detail" not in response.data:
            # Keep validation field errors while ensuring predictable top-level message
            response.data = {
                "detail": "Dữ liệu không hợp lệ hoặc thao tác bị từ chối.",
                "errors": response.data,
            }
        elif isinstance(response.data, list):
            response.data = {
                "detail": str(response.data[0]) if response.data else "Đã có lỗi xảy ra.",
                "errors": response.data,
            }
    else:
        logger.exception("Unhandled exception in API view: %s", exc)
    return response
