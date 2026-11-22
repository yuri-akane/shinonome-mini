import math
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

# Regular expression to detect suspicious Unicode characters:
#   - ASCII control characters (U+0000–U+001F) and DEL (U+007F)
#   - C1 control characters (U+0080–U+009F: e.g. CSI U+009B, OSC U+009D)
#   - Zero‑width characters: ZWSP, ZWNJ, ZWJ, LRM, RLM (U+200B–U+200F)
#   - Bidirectional control characters: LRE, RLE, PDF, LRO, RLO (U+202A–U+202E)
#   - Bidirectional isolate characters: LRI, RLI, FSI, PDI (U+2066–U+2069)
#   - BOM / Zero Width No‑Break Space (U+FEFF)
_SUSPICIOUS_UNICODE_RE = re.compile(
    r'[\x00-\x1f'      # ASCII制御文字 (NUL〜US)
    r'\x7f'            # DEL
    r'\u0080-\u009f'    # C1制御文字 (PAD〜APC: CSIやOSC等)
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


def is_binary_file(file_path: str | Path, block_size: int = 8192) -> bool:
    """Return True if the file contains NUL bytes (b'\\x00') in its leading bytes or entire file."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(block_size)
            return b'\x00' in chunk
    except Exception:
        return True


# ---------------------------------------------------------------------------
# 安全な数値変換ヘルパー
# ---------------------------------------------------------------------------

def safe_float(
    val: Any,
    *,
    min_val: float | None = None,
    max_val: float | None = None,
    default: float | None = None,
) -> float | None:
    """任意の値を安全に float へ変換する。

    以下のいずれかに該当する場合は *default* を返す:
      - ``bool`` 型（Python では ``isinstance(True, int)`` が ``True`` になるため明示的に除外）
      - ``int`` / ``float`` 以外の型（文字列・リスト・dict 等）
      - NaN, +Infinity, -Infinity（``math.isfinite`` で検出）
      - ``min_val`` / ``max_val`` で指定した範囲外

    Parameters
    ----------
    val:
        変換対象の値。JSON や BMS ヘッダーから読み込んだ任意の型を想定。
    min_val:
        許容する最小値（閉区間）。``None`` のときはチェックしない。
    max_val:
        許容する最大値（閉区間）。``None`` のときはチェックしない。
    default:
        無効値だったときの返り値。
        ``None``（デフォルト）を返すと、呼び出し元で ``if v is None: continue``
        のようなスキップ処理が書ける。
        具体的な数値を渡せばフォールバック値として機能する。

    Returns
    -------
    float | None
    """
    # ① bool を除外（True/False が 1/0 として通り抜けるのを防ぐ）
    if isinstance(val, bool):
        return default
    # ② 数値型チェック
    if not isinstance(val, (int, float)):
        return default
    # ③ NaN / ±Inf を弾く
    if not math.isfinite(val):
        return default
    # ④ 範囲チェック（指定がある場合のみ）
    if min_val is not None and val < min_val:
        return default
    if max_val is not None and val > max_val:
        return default
    return float(val)


def safe_int(
    val: Any,
    *,
    min_val: int | None = None,
    max_val: int | None = None,
    default: int | None = None,
) -> int | None:
    """任意の値を安全に int へ変換する（切り捨て）。

    内部で :func:`safe_float` を通してから ``int()`` で変換する。
    四捨五入が必要な場合は呼び出し元で ``round()`` してから渡すこと。

    Parameters / Returns は :func:`safe_float` と同様。
    """
    float_min = float(min_val) if min_val is not None else None
    float_max = float(max_val) if max_val is not None else None
    float_default = float(default) if default is not None else None
    result = safe_float(val, min_val=float_min, max_val=float_max, default=float_default)
    if result is None:
        return default
    return int(result)

