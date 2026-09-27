"""
turn the raw traceback text into a list of frames.
no external deps, just regex - a traceback is not that scary
"""
import re

from app.models import Frame, TracebackInfo

# File "/path/to/file.py", line 12, in main
# in 3.11+ a SyntaxError frame may have no ", in func" part
FRAME_RE = re.compile(r'^\s*File "(?P<file>.+)", line (?P<line>\d+)(?:, in (?P<func>.+?))?\s*$')

# the exception line has zero indentation: KeyError: 'user_id'
EXC_RE = re.compile(
    r"^(?P<type>[A-Za-z_][\w.]*)"
    r"(?::\s?(?P<msg>.*))?$"
)

# 3.11+ draws carets under the guilty line
CARET_RE = re.compile(r"^\s*[~^]+\s*$")

IGNORE_LINES = (
    "Traceback (most recent call last):",
    "During handling of the above exception, another exception occurred:",
    "The above exception was the direct cause of the following exception:",
)


def _is_pseudo(path: str) -> bool:
    # <stdin>, <string>, <frozen importlib._bootstrap> and other non-file stuff
    return path.startswith("<") and path.endswith(">")


def parse_traceback(text: str) -> TracebackInfo:
    """
    pulls frames and the last exception out of the raw traceback text.
    chained exceptions are not a problem - we take the final (last) exception.
    """
    info = TracebackInfo()
    lines = text.splitlines()

    exc_type = ""
    exc_message = ""

    i = 0
    while i < len(lines):
        line = lines[i]
        match = FRAME_RE.match(line)
        if match:
            file = match.group("file")
            func = match.group("func") or ""
            frame = Frame(
                file=file,
                line=int(match.group("line")),
                func=func.strip(),
                pseudo=_is_pseudo(file),
            )
            # the next line is the source code, unless it is a caret line
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt[:1] in (" ", "\t") and not CARET_RE.match(nxt) and not FRAME_RE.match(nxt):
                    frame.source = nxt.strip()
            info.frames.append(frame)
        else:
            stripped = line.strip()
            if line[:1] not in (" ", "\t") and stripped and stripped not in IGNORE_LINES:
                exc = EXC_RE.match(stripped)
                if exc:
                    # the last match is the final exception of the chain
                    exc_type = exc.group("type")
                    exc_message = (exc.group("msg") or "").strip()
        i += 1

    # depth: the last frame is the exception point = 1.0, the first one = 0.0
    total = len(info.frames)
    for idx, frame in enumerate(info.frames):
        frame.depth = 1.0 if total <= 1 else idx / (total - 1)

    info.exc_type = exc_type
    info.exc_message = exc_message
    return info
