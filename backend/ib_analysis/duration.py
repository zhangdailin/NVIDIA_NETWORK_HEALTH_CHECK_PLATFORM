"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""

import re
from datetime import datetime
from dateutil import tz

DURATION_CACHE = 1.0

def extract_duration(filename: str=None):
    global DURATION_CACHE

    if not filename:
        return DURATION_CACHE

    count = 0
    pattern = r'--pm_pause_time (\d+)'
    with open(filename, 'r', encoding='latin-1') as file:
        for line in file:
            count += 1
            if count > 30: # we exepct to see the duration in the first few lines!
                break
            # Search for the pattern in the current line
            match = re.search(pattern, line)
            # If a match is found, extract the number
            if match:
                DURATION_CACHE = float(match.group(1))
                return DURATION_CACHE
    return DURATION_CACHE


def extract_timestamp(filename: str):
    count = 0
    with open(filename, 'r', encoding='latin-1') as file:
        content = ""
        for line in file:
            count += 1
            if count > 10: # we exepct to see the duration in the first few lines!
                break
            content = f"{content} {line}"
    try:
        return convert_timestamp_to_ist(content)
    except Exception:
        return "NA"


def convert_timestamp_to_ist(text):
    """
    Searches for a timestamp in the form:
        YYYY-MM-DD HH:MM:SS (UTC|IST|...) ±HHMM

    Parses it (using the offset ±HHMM) and converts to IST (Asia/Kolkata).
    Returns the converted time as a string, or None if no match is found.
    """
    pattern = (
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"   # timestamp
        r"[A-Z]{3}\s+"                                   # any 3-letter TZ abbrev.
        r"([+\-]\d{4})"                                  # numeric offset
    )

    match = re.search(pattern, text)
    if not match:
        return None

    # Rebuild the datetime string *without* the literal UTC/IST text,
    # since strptime will parse the offset directly.
    dt_str = f"{match.group(1)} {match.group(2)}"

    # Parse the datetime with its offset (e.g., +0000, +0530, etc.)
    dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S %z")

    # Convert to IST (Asia/Kolkata)
    ist_zone = tz.gettz("Asia/Kolkata")
    dt_ist = dt_obj.astimezone(ist_zone)

    # Return in desired format (you can change the format as needed)
    return dt_ist.strftime("%Y-%m-%d %H:%M:%S %Z %z")
