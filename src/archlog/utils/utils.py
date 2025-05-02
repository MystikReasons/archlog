import os
import subprocess
from datetime import datetime, timezone


def get_datetime_now(format: str) -> str:
    return datetime.now(timezone.utc).strftime(format)
