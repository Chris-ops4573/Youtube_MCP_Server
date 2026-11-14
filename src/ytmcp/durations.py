import re

_PATTERN = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)

def parse_duration(value: str) -> int:
    """Convert an ISO 8601 duration like 'PT1H4M30S' to seconds.
    Raises ValueError for invalid input."""
    match = _PATTERN.match(value.strip()) if value else None
    if not match or not any(match.groupdict().values()):
        raise ValueError(f"Invalid ISO 8601 duration: {value!r}")
    parts = {k: int(v or 0) for k, v in match.groupdict().items()}
    return (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )