from rest_framework.exceptions import ValidationError


def format_serializer_error(exc: ValidationError, fallback: str = "Dữ liệu không hợp lệ.") -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        for key, val in detail.items():
            msg = val[0] if isinstance(val, list) and val else val
            if key == "non_field_errors":
                return str(msg)
            return f"{key}: {msg}"
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail) if detail else fallback
