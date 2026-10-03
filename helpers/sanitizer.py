import re
import unicodedata
from pathlib import Path, PurePosixPath

# Regular expression to detect suspicious Unicode characters:
#   - ASCII control characters (U+0000–U+001F) and DEL (U+007F)
#   - Zero‑width characters: ZWSP, ZWNJ, ZWJ, LRM, RLM (U+200B–U+200F)
#   - Bidirectional control characters: LRE, RLE, PDF, LRO, RLO (U+202A–U+202E)
#   - Bidirectional isolate characters: LRI, RLI, FSI, PDI (U+2066–U+2069)
#   - BOM / Zero Width No‑Break Space (U+FEFF)
_SUSPICIOUS_UNICODE_RE = re.compile(
    r'[\x00-\x1f'      # ASCII制御文字 (NUL〜US)
    r'\x7f'            # DEL
    r'\u200b-\u200f'    # ゼロ幅文字 (ZWSP, ZWNJ, ZWJ, LRM, RLM)
    r'\u202a-\u202e'    # 方向性制御文字 (LRE, RLE, PDF, LRO, RLO)
    r'\u2066-\u2069'    # 方向性分離文字 (LRI, RLI, FSI, PDI)
    r'\ufeff'           # BOM / ZWNBSP
    r']'
)


def has_suspicious_chars(s: str) -> bool:
    """Return True if *s* contains suspicious Unicode characters."""
    if not isinstance(s, str):
        return False
    return bool(_SUSPICIOUS_UNICODE_RE.search(s))


def sanitize_display_string(s: str) -> str:
    """Strip suspicious Unicode characters from *s* for safe display."""
    if not isinstance(s, str):
        return ""
    return _SUSPICIOUS_UNICODE_RE.sub('', s)


def sanitize_file_path(raw_path: str | Path | None, check_exists: bool = True) -> Path | None:
    """
    Sanitize a raw file path string or Path object.
    - Normalizes slashes (`\\` -> `/`) and strips whitespace
    - Rejects suspicious Unicode characters
    - Checks for NFKC traversal tricks (`..` disguised in Unicode)
    - Checks for `..` path traversal segments
    - If check_exists is True, verifies that the path exists and is a file
    Returns resolved Path object if valid, or None if invalid or unsafe.
    """
    if raw_path is None:
        return None

    path_str = str(raw_path).replace('\\', '/').strip()
    if not path_str:
        return None

    if has_suspicious_chars(path_str):
        return None

    # NFKC traversal check
    nfkc_path = unicodedata.normalize('NFKC', path_str).replace('\\', '/')
    for part in nfkc_path.split('/'):
        if part == '..':
            return None

    try:
        p = Path(path_str).expanduser()
        posix_parts = PurePosixPath(p.as_posix()).parts
        for part in posix_parts:
            if part == '..':
                return None

        if check_exists:
            if not p.exists() or not p.is_file():
                return None
            return p.resolve()
        return p
    except Exception:
        return None
