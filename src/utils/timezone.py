from datetime import datetime, timedelta

def get_current_time():
    """Return the current time in SAST (UTC+2) as a naive datetime."""
    return datetime.utcnow() + timedelta(hours=2)