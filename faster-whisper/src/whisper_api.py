from __future__ import annotations

import json
from typing import Iterable, List


def iter_sse_data(lines: Iterable[bytes]) -> Iterable[str]:
    data_lines: List[str] = []
    for raw in lines:
        if raw is None:
            continue
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                yield "\n".join(data_lines)
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())
    if data_lines:
        yield "\n".join(data_lines)
