from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def load_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip('"').strip("'")
        values[clean_key] = clean_value
        os.environ.setdefault(clean_key, clean_value)

    return values
