import re


def breakout_filenames(filename: str):
    """Pulls metadata out of a DTD rail data filename"""
    return {
        "name": filename,
        "number": re.sub(r"[^0-9]", "", filename),
        "type": re.sub(r"[^A-Z]", "", filename),
    }
