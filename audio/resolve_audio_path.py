import os

from config import get_filename_variants, normalize_filename_chars

def resolve_audio_path(base_path: str, relative_file_name: str) -> str | None:
    """
    指定されたベースパスと相対ファイル名から実際の音源ファイルパスを解決する。
    - パス区切り (\\) を / に統一
    - 特殊文字（波ダッシュ、ダッシュ、マイナス記号等）の表記揺れバリエーション検索
    - 拡張子フォールバック順 (.wav -> .ogg -> .flac -> .mp3 -> 元の拡張子)
    - ディレクトリ内スキャンによる文字正規化・大文字小文字無視曖昧一致
    """
    relative_file_name = sanitize_wav_path(relative_file_name)
    if not relative_file_name:
        return None

    rel_path = relative_file_name.replace('\\', '/')
    full_target = os.path.join(base_path, rel_path)

    dir_name, base_name = os.path.split(full_target)
    stem, ext = os.path.splitext(base_name)

    # 試行する拡張子の優先順位 (.wav -> .ogg -> .flac -> .mp3 -> 元の拡張子)
    candidate_exts = ['.wav', '.ogg', '.flac', '.mp3']
    if ext and ext.lower() not in candidate_exts:
        candidate_exts.append(ext.lower())

    # 1. 互換文字バリエーション (波ダッシュ、ダッシュ、マイナス記号等)
    stem_variants = get_filename_variants(stem)

    # 1-A. 直接存在判定
    for e in candidate_exts:
        ext_patterns = [e, e.upper()] if e.islower() else [e, e.lower()]
        for st in stem_variants:
            for ep in ext_patterns:
                cand_path = os.path.join(dir_name, st + ep)
                if os.path.exists(cand_path):
                    return cand_path

    # 2. ディレクトリ内スキャンによるフォールバック
    if os.path.isdir(dir_name):
        try:
            files_in_dir = os.listdir(dir_name)
        except OSError:
            files_in_dir = []

        norm_target_stem = normalize_filename_chars(stem).lower()
        norm_candidate_exts = [e.lower() for e in candidate_exts]

        for target_ext in norm_candidate_exts:
            for real_fname in files_in_dir:
                real_stem, real_ext = os.path.splitext(real_fname)
                if normalize_filename_chars(real_stem).lower() == norm_target_stem and real_ext.lower() == target_ext:
                    return os.path.join(dir_name, real_fname)

    return None

import re
import unicodedata
from pathlib import PurePosixPath

# Regular expression to detect Windows invalid filename characters.
_INVALID_CHARS_RE = re.compile(r'[<>:"|?*]')

# Allowed audio file extensions (lower‑case).
_ALLOWED_EXTENSIONS = {'.wav', '.ogg', '.mp3', '.flac'}

_MAX_PATH_LENGTH = 250

# Suspicious Unicode characters that should never appear in a file path:
#   - ASCII control characters (U+0000–U+001F) and DEL (U+007F)
#   - Zero‑width characters: ZWSP, ZWNJ, ZWJ, LRM, RLM (U+200B–U+200F)
#   - Bidirectional control characters: LRE, RLE, PDF, LRO, RLO (U+202A–U+202E)
#   - Bidirectional isolate characters: LRI, RLI, FSI, PDI (U+2066–U+2069)
#   - BOM / Zero Width No‑Break Space (U+FEFF)
_SUSPICIOUS_UNICODE_RE = re.compile(
    r'[\x00-\x1f'     # ASCII制御文字 (NUL〜US)
    r'\x7f'            # DEL
    r'\u200b-\u200f'   # ゼロ幅文字 (ZWSP, ZWNJ, ZWJ, LRM, RLM)
    r'\u202a-\u202e'   # 方向性制御文字 (LRE, RLE, PDF, LRO, RLO)
    r'\u2066-\u2069'   # 方向性分離文字 (LRI, RLI, FSI, PDI)
    r'\ufeff'          # BOM / ZWNBSP
    r']'
)

"""
Utility for sanitizing WAV paths referenced in BMS files.

1. Normalise slashes (`\\` → `/`) and strip surrounding whitespace.
1a. Reject paths containing suspicious Unicode characters (control chars,
    zero‑width spaces, bidirectional controls, BOM).
1b. Apply NFKC normalisation to a copy of the path and reject it if `..`
    or path separators appear after normalisation (Unicode disguise check).
2. Reject absolute paths (starting with '/' or containing a drive letter).
3. Resolve `.` segments and reject any `..` segment that would escape
   the base directory.
4. Ensure the path contains only allowed characters:
   - No Windows invalid filename characters: `< > : " | ? *`
5. Enforce a whitelist of audio extensions: `.wav`, `.ogg`, `.mp3`,
   `.flac` (case‑insensitive).
6. Limit total length to 255->250 characters (common filesystem limit).
"""
def sanitize_wav_path(raw_path: str) -> str | None:
    """Sanitize a raw WAV path extracted from a BMS file."""
    if not isinstance(raw_path, str):
        return None

    # 1. Normalise slashes and strip whitespace.
    path = raw_path.replace('\\', '/').strip()

    # Empty string after stripping is invalid.
    if not path:
        return None

    # 1a. Reject suspicious Unicode characters.
    #     These include control characters, zero‑width spaces, bidirectional
    #     control/isolate characters, and BOM — none of which have a legitimate
    #     use in a file path and could be used to obscure malicious content.
    if _SUSPICIOUS_UNICODE_RE.search(path):
        return None

    # 1b. NFKC traversal check.
    #     Apply Unicode NFKC normalisation to a *copy* of the path and verify
    #     that no `..` or path‑separator characters appear after normalisation.
    #     This catches tricks such as using FULLWIDTH FULL STOPs (U+FF0E) or
    #     FULLWIDTH SOLIDUS (U+FF0F) to disguise traversal sequences.
    #     The original `path` is NOT modified so that the actual filename on
    #     disk (which may use non‑ASCII characters) can still be found.
    nfkc_path = unicodedata.normalize('NFKC', path)
    nfkc_path_normalised_seps = nfkc_path.replace('\\', '/')
    for nfkc_part in nfkc_path_normalised_seps.split('/'):
        if nfkc_part == '..':
            return None

    # 2. Reject absolute paths.
    #   - Unix absolute: starts with '/'
    #   - Windows drive letter: contains ':' before any slash
    if path.startswith('/') or re.match(r'^[A-Za-z]:', path):
        return None

    # 3. Resolve '.' segments and reject '..'.
    parts = []
    for part in PurePosixPath(path).parts:
        if part == '' or part == '.':
            continue
        if part == '..':
            # Attempting to escape the base directory.
            return None
        parts.append(part)

    if not parts:
        # Path resolved to empty (e.g., only '.' segments).
        return None

    sanitized = PurePosixPath(*parts).as_posix()

    # 4. Check for invalid characters in each component.
    for part in sanitized.split('/'):
        if _INVALID_CHARS_RE.search(part):
            return None

    # 5. Enforce allowed extensions.
    ext = PurePosixPath(sanitized).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return None

    # 6. Length check (total path length).
    if len(sanitized) > _MAX_PATH_LENGTH:
        return None

    return sanitized
