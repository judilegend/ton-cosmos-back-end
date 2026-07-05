from datetime import datetime


def parse_birth_time(value: str | None):
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.time()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value).time()
    except ValueError:
        return None
