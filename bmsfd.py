#!/usr/bin/env python3
"""
A tiny fd‑like directory browser written with only the standard library.
No database, no external dependencies.

Usage:
    python3 bmsfd.py [start_dir]

If *start_dir* is omitted, the first allowed root from settings.toml is used,
or a virtual root that lists all allowed roots if none are specified.
"""

import curses
from pathlib import Path
import re
import sys
import subprocess
import unicodedata
import json
from collections import defaultdict

# ---------------------------------------------------------------------------
# Suspicious Unicode character detection
# (mirrors the pattern defined in audio/resolve_audio_path.py)
# ---------------------------------------------------------------------------
# Characters that have no legitimate use in a file path or display string and
# could be used to confuse the terminal or obscure malicious content:
#   - ASCII control characters (U+0000–U+001F) and DEL (U+007F)
#   - Zero‑width characters: ZWSP, ZWNJ, ZWJ, LRM, RLM (U+200B–U+200F)
#   - Bidirectional control characters: LRE, RLE, PDF, LRO, RLO (U+202A–U+202E)
#   - Bidirectional isolate characters: LRI, RLI, FSI, PDI (U+2066–U+2069)
#   - BOM / Zero Width No‑Break Space (U+FEFF)
_SUSPICIOUS_UNICODE_RE = re.compile(
    r'[\x00-\x1f'      # ASCII制御文字 (NUL〜US)
    r'\x7f'             # DEL
    r'\u200b-\u200f'    # ゼロ幅文字 (ZWSP, ZWNJ, ZWJ, LRM, RLM)
    r'\u202a-\u202e'    # 方向性制御文字 (LRE, RLE, PDF, LRO, RLO)
    r'\u2066-\u2069'    # 方向性分離文字 (LRI, RLI, FSI, PDI)
    r'\ufeff'           # BOM / ZWNBSP
    r']'
)


def has_suspicious_chars(s: str) -> bool:
    """Return True if *s* contains suspicious Unicode characters."""
    return bool(_SUSPICIOUS_UNICODE_RE.search(s))


def sanitize_display_string(s: str) -> str:
    """Strip suspicious Unicode characters from *s* for safe curses display."""
    return _SUSPICIOUS_UNICODE_RE.sub('', s)

# Supported song file extensions (case‑insensitive)
SUPPORTED_EXTENSIONS = {".bms", ".bme", ".bml", ".pms", ".bmson"}

# Placeholder structure for future file properties (kept for compatibility)
file_props = defaultdict(lambda: {
    "title": "",
    "subtitle": "",
    "artist": "",
    "subartist": "",
    "genre": "",
    "playlevel": "",
    "bpm": ""
})

def parse_song_file(path: Path, encoding: str = "cp932") -> dict:
    """
    Read a plain‑text song file and extract the following keys if present:
        #TITLE, #SUBTITLE, #ARTIST, #SUBARTIST, #GENRE, #PLAYLEVEL, #BPM,
        #DIFFICULTY, #LEVEL
    For .bmson files (JSON format) the same keys are extracted from the JSON object.
    """
    props = {}
    ext = path.suffix.lower()
    if ext == ".bmson":
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            info = data.get("info", {})
            # Basic string fields
            for key in ("title", "subtitle", "artist"):
                val = info.get(key)
                if isinstance(val, str):
                    props[key] = val.strip()
            # Sub‑artists: take the first entry if available
            subarts = info.get("subartists")
            if isinstance(subarts, list) and subarts:
                first = subarts[0]
                if isinstance(first, str):
                    props["subartist"] = first.strip()
            # Genre
            genre = info.get("genre")
            if isinstance(genre, str):
                props["genre"] = genre.strip()
            # Play level (level field in bmson)
            level = info.get("level")
            if isinstance(level, (int, float)):
                props["playlevel"] = str(level)
            # BPM (init_bpm field in bmson)
            init_bpm = info.get("init_bpm")
            if isinstance(init_bpm, (int, float)):
                props["bpm"] = str(init_bpm)
        except Exception:
            # Malformed JSON or read error; ignore and return empty dict
            pass
    else:
        try:
            with path.open("r", encoding=encoding, errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith("#"):
                        continue
                    parts = line[1:].split(None, 1)  # remove leading '#'
                    if len(parts) != 2:
                        continue
                    key, val = parts
                    key_lower = key.lower()
                    if key_lower in props:  # already set
                        continue
                    # Keep all keys that the tests expect and those we want to display.
                    if key_lower in ("title", "subtitle", "artist",
                                     "subartist", "genre", "playlevel", "bpm",
                                     "difficulty", "level"):
                        props[key_lower] = val.strip()
        except Exception:
            pass  # ignore unreadable files
    return props

# ----------------------------------------------------------------------
def load_settings() -> dict:
    """
    Load allowed root directories from settings.toml in the repository root.
    If the file or key is missing, all paths are considered allowed.
    Also reads the BMS encoding setting and launchers configuration.
    """
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib

    repo_root = Path(__file__).resolve().parent
    settings_file = repo_root / "settings.toml"
    default_launchers = {
        "default": "cnnm",
        "cnnm": {"name": "Shinonome Mini (cnnm.py)", "command": ["python3", "cnnm.py", "{file}"]}
    }
    if not settings_file.exists():
        return {"roots": set(), "encoding": "cp932", "launchers": default_launchers}

    try:
        with settings_file.open("rb") as f:
            data = tomllib.load(f)
    except Exception:  # pragma: no cover
        return {"roots": set(), "encoding": "cp932", "launchers": default_launchers}

    roots = data.get("allowed_roots", [])
    allowed = set()
    for r in roots:
        p = (repo_root / r).resolve()
        allowed.add(p)

    encoding = data.get("bms", {}).get("encoding", "cp932")
    launchers = data.get("launchers", default_launchers)
    if "default" not in launchers:
        launchers["default"] = "cnnm"
    if "cnnm" not in launchers:
        launchers["cnnm"] = default_launchers["cnnm"]

    return {"roots": allowed, "encoding": encoding, "launchers": launchers}

def is_allowed(target: Path, allowed_roots: set[Path]) -> bool:
    """
    Return True if target is within one of the allowed root directories.
    If allowed_roots is empty, all paths are considered allowed.
    """
    if not allowed_roots:
        return True
    try:
        # Python 3.9+
        for root in allowed_roots:
            if target.is_relative_to(root):
                return True
    except AttributeError:  # pragma: no cover
        # Fallback for older Python versions
        for root in allowed_roots:
            try:
                target.relative_to(root)
                return True
            except ValueError:
                continue
    return False

# ----------------------------------------------------------------------
def launch_external_app(stdscr, cmd_template: list[str] | str, path: Path) -> tuple[curses.window, str | None]:
    """
    Temporarily leave curses mode to run an external launcher/player on *path*.
    *cmd_template* can be a list of strings or a string containing '{file}'.
    After the process exits, re-enter curses and restore the terminal state.
    Returns (new_stdscr, error_message).
    """
    if not path.exists() or not path.is_file():
        return stdscr, "Error: Selected item is not a valid file."
    if has_suspicious_chars(str(path)):
        return stdscr, "Error: File path contains suspicious characters."

    # Format the command arguments
    if isinstance(cmd_template, str):
        cmd = [cmd_template.format(file=str(path))]
    elif isinstance(cmd_template, list):
        cmd = [arg.format(file=str(path)) for arg in cmd_template]
    else:
        return stdscr, "Error: Invalid launcher command configuration."

    curses.endwin()
    err_msg = None
    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        err_msg = f"Error: Command not found ({cmd[0]})"
    except Exception as e:
        err_msg = f"Error launching app: {e}"
    finally:
        new_stdscr = curses.initscr()
        curses.curs_set(0)
    return new_stdscr, err_msg


def open_file_with_cnnm(stdscr, path: Path) -> curses.window:
    """Compatibility wrapper that launches cnnm on the given file."""
    new_stdscr, _ = launch_external_app(stdscr, ["python3", "cnnm.py", "{file}"], path)
    return new_stdscr

# ----------------------------------------------------------------------
def collect_bms_files(root: Path) -> list[Path]:
    """
    Return a sorted list of all BMS‑type files under *root* (recursively).
    Paths are relative to the root for display purposes.
    """
    return sorted(
        (p for p in root.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=lambda p: str(p.relative_to(root)).lower()
    )

# ----------------------------------------------------------------------
def navigate_up(
    current_path: Path,
    current_selected: int,
    last_selected: dict[Path, int],
    allowed_roots: set[Path],
) -> tuple[Path, int, int, None, None]:
    """
    Navigate to the parent directory, respecting allowed_roots.
    Mutates *last_selected* to save the current cursor position before moving.
    Returns (path, selected, offset, preview_lines, preview_file).
    """
    last_selected[current_path] = current_selected
    new_path = current_path.parent
    if is_allowed(new_path, allowed_roots):
        return new_path, last_selected.get(new_path, 0), 0, None, None
    # Parent is outside allowed roots → fall back to the virtual root.
    return Path("/"), 0, 0, None, None


# ----------------------------------------------------------------------
def build_entries(
    path: Path,
    allowed_roots: set[Path],
) -> tuple[list[Path], str | None]:
    """
    Build the list of directory entries to display for *path*.
    Returns (entries, error_msg). *error_msg* is None on success.
    The virtual root (Path("/")) returns the allowed roots as top-level entries.
    """
    if path == Path("/"):
        return sorted(allowed_roots, key=lambda p: p.name.lower()), None
    try:
        raw_entries = [
            p for p in path.iterdir()
            if p.is_dir() or p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    except (FileNotFoundError, PermissionError):
        return [Path("..")], f"Error: Cannot access directory ({path})"
    for p in raw_entries:
        if not p.is_dir():
            _ = file_props[p]  # populate placeholder properties (no-op yet)
    return (
        [Path("..")] + sorted(raw_entries, key=lambda p: (not p.is_dir(), p.name.lower())),
        None,
    )


def make_preview_lines(target_path: Path, is_dir: bool, encoding: str) -> list[str] | None:
    """
    Generate preview lines for a given file or directory path.
    For song files, parses metadata. For directories, lists contained song files.
    """
    if not is_dir and target_path.suffix.lower() in SUPPORTED_EXTENSIONS:
        try:
            props = parse_song_file(target_path, encoding)
            lines = []
            order = ["genre", "title", "subtitle", "artist",
                     "subartist", "playlevel", "bpm"]
            for key in order:
                val = props.get(key, "")
                if val:
                    lines.append(f"{key.title()}: {sanitize_display_string(val)}")
                else:
                    lines.append("")
            return lines
        except Exception:
            return None
    elif is_dir:
        try:
            bms_files = sorted(
                (p for p in target_path.iterdir()
                 if p.suffix.lower() in SUPPORTED_EXTENSIONS),
                key=lambda p: p.name.lower()
            )
            return [f"{p.name}" for p in bms_files]
        except Exception:
            return None
    return None


def draw_preview(stdscr, preview_lines: list[str] | None, prop_start_row: int, prop_rows: int, w: int):
    """Draw preview lines in the designated curses preview area."""
    if preview_lines is not None and prop_rows > 0:
        for i, line in enumerate(preview_lines):
            if i >= prop_rows:
                break
            try:
                stdscr.addnstr(prop_start_row + i, 0, f"{line}", w - 1, curses.A_BOLD)
            except curses.error:
                pass


# ----------------------------------------------------------------------
def main(stdscr):
    # --------------------------------------------------------------
    # 1. Initialise state
    # --------------------------------------------------------------
    config = load_settings()
    allowed_roots = config["roots"]
    encoding = config.get("encoding", "cp932")

    config_msg = None
    if not allowed_roots:
        # No settings found; fall back to current directory and warn user.
        allowed_roots = {Path.cwd().resolve()}
        config_msg = ("No allowed_roots found in settings.toml; "
                      "using current directory. Please configure settings.")

    # Determine initial path: if a command‑line argument is given, use it;
    # otherwise show a virtual root that lists all allowed roots.
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if has_suspicious_chars(arg):
            # Reject command‑line arguments containing suspicious Unicode chars.
            path = Path("/")
        else:
            path = Path(arg).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                path = Path("/")
            elif allowed_roots and not is_allowed(path, allowed_roots):
                # The given path is outside every configured allowed root,
                # but the user explicitly specified it on the command line.
                # Add it to allowed_roots for this session so navigation
                # within the directory works normally (Enter / Backspace etc.)
                # while the rest of the filesystem remains restricted.
                allowed_roots.add(path)
    else:
        # Use a sentinel Path("/") to represent the virtual root
        path = Path("/")

    selected = 0
    offset = 0

    # --- state for on‑demand preview ------------------------------------
    preview_lines: list[str] | None = None   # lines to show in the prop area
    preview_file: Path | None = None          # file currently being previewed (kept for compatibility)

    # ------------------------------------------------------------------
    # New state for lazy loading and position memory
    # ------------------------------------------------------------------
    last_selected: dict[Path, int] = {}

    # State for list mode toggle
    list_mode = False          # whether we are showing the recursive BMS list
    bms_list: list[Path] | None = None  # cached list of files when in list mode

    # State for status / error message
    status_msg: str | None = None

    launchers = config.get("launchers", {})
    default_launcher_key = launchers.get("default", "cnnm")
    default_launcher_cfg = launchers.get(default_launcher_key, {})
    default_cmd_template = default_launcher_cfg.get("command", ["python3", "cnnm.py", "{file}"])

    # --------------------------------------------------------------
    # 2. Main event loop
    # --------------------------------------------------------------
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # --- show current path ------------------------------------
        if path == Path("/"):
            stdscr.addstr(0, 0, "Roots:", curses.A_BOLD)
        else:
            stdscr.addstr(0, 0, f"Path: {path}", curses.A_BOLD)

        # Show configuration warning or status error message if present
        display_msg = status_msg or config_msg
        if display_msg:
            try:
                attr = curses.A_BOLD if status_msg else curses.A_DIM
                stdscr.addnstr(1, 0, display_msg, w-1, attr)
            except curses.error:
                pass

        # Hide the cursor for a cleaner UI
        try:
            curses.curs_set(0)
        except Exception:
            pass

        # ------------------------------------------------------------------
        # Layout:
        #   0          : Path / Allowed Roots header
        #   1 (optional): config message / status error
        #   2/3       : blank line(s) separator
        #   preview area
        #   entries start here
        #   last row   : help line
        # ------------------------------------------------------------------
        top_offset = 0

        msg_rows = 1 if display_msg else 0
        prop_start_row = msg_rows + 1
        prop_rows = min(7, max(h - prop_start_row - 2, 0))  # leave last line for help
        entry_start_row = prop_start_row + prop_rows + 1   # one blank line after preview

        if entry_start_row > h - 2:          # leave last line for help
            overflow = entry_start_row - (h - 2)
            prop_rows -= overflow
            if prop_rows < 0:
                prop_rows = 0
            entry_start_row = h - 3   # keep one blank line before help

        max_entry_rows = max(0, h - entry_start_row - 1)   # reserve last line for help

        # Store current path to detect changes after key handling
        old_path = path

        # --- build entry list: directories + supported song files
        if list_mode:
            # In list mode we show the recursive BMS file list
            entries = bms_list or []
        else:
            entries, err = build_entries(path, allowed_roots)
            if err:
                status_msg = err

        # Ensure selected index is within bounds after entries are known
        if selected >= len(entries):
            selected = max(0, len(entries) - 1)

        # ------------------------------------------------------------------
        # Clamp selected / offset so that the cursor is always visible after a resize
        # ------------------------------------------------------------------
        if offset > selected:
            offset = selected
        elif selected >= offset + max_entry_rows:
            offset = selected - max_entry_rows + 1

        displayed_entries = min(len(entries) - offset, max_entry_rows)

        # --- draw entries -----------------------------------------
        for idx, ent in enumerate(entries[offset:offset+displayed_entries]):
            if list_mode:
                # Show relative path without numbering
                line = str(ent.relative_to(path))
            else:
                if path == Path("/"):
                    line = f"{ent.name}/"
                else:
                    line = f"{ent.name}/" if ent.is_dir() else ent.name
            attr = curses.A_REVERSE if (offset + idx) == selected else curses.A_NORMAL
            stdscr.addstr(entry_start_row + idx, 0, line[: w-1], attr)

        # ------------------------------------------------------------------
        # Update preview automatically for current selection
        # ------------------------------------------------------------------
        sel_entry = entries[selected] if entries else None
        if path != Path("/") and sel_entry:
            if not list_mode:
                target = path / sel_entry
                preview_lines = make_preview_lines(target, sel_entry.is_dir(), encoding)
            else:
                # In list mode, sel_entry is a file path
                preview_lines = make_preview_lines(sel_entry, False, encoding)
        else:
            preview_lines = None

        # Draw preview area
        draw_preview(stdscr, preview_lines, prop_start_row, prop_rows, w)

        # ------------------------------------------------------------------
        # Help / key‑function legend at the bottom line (row h‑1)
        # ------------------------------------------------------------------
        help_msg = f"Esc: quit | Backspace/..: up | Enter: open dir / play ({default_launcher_key}) | L: list all (toggle)"
        try:
            stdscr.addnstr(h - 1, 0, help_msg, w-1, curses.A_DIM)
        except curses.error:
            # terminal too small to show the help line; ignore
            pass

        stdscr.refresh()

        # --- key handling -----------------------------------------
        key = stdscr.getch()
        if key in (curses.KEY_EXIT, 27):          # ESC
            break
        elif list_mode:
            # Navigation within list mode
            if key in (curses.KEY_UP, ord('k')):
                selected = max(0, selected - 1)
            elif key in (curses.KEY_DOWN, ord('j')):
                selected = min(len(entries) - 1, selected + 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                chosen = entries[selected]
                if not chosen.is_dir():
                    stdscr, status_msg = launch_external_app(stdscr, default_cmd_template, chosen)
            elif key == ord('l'):
                # Toggle off list mode
                list_mode = False
                bms_list = None
        else:
            if key in (curses.KEY_UP, ord('k')):
                selected = max(0, selected - 1)
                if selected < offset:
                    offset = selected
            elif key in (curses.KEY_DOWN, ord('j')):
                selected = min(len(entries) - 1, selected + 1)
                if selected >= offset + max_entry_rows:
                    offset = selected - max_entry_rows + 1
            elif key in (curses.KEY_ENTER, 10, 13):
                chosen = entries[selected]
                if path == Path("/") and chosen.is_dir():
                    # Enter a real directory from the virtual root
                    new_path = chosen.resolve()
                    if not new_path.exists() or not new_path.is_dir():
                        status_msg = f"Error: Directory does not exist ({chosen.name})"
                    elif is_allowed(new_path, allowed_roots):
                        status_msg = None
                        last_selected[path] = selected
                        path = new_path
                        selected = last_selected.get(path, 0)
                        offset = 0
                        preview_lines = None          # clear any existing preview
                        preview_file = None
                else:
                    if chosen.name == "..":
                        status_msg = None
                        path, selected, offset, preview_lines, preview_file = navigate_up(
                            path, selected, last_selected, allowed_roots
                        )
                    else:
                        new_path = path / chosen
                        if not new_path.exists():
                            status_msg = f"Error: Directory does not exist ({chosen.name})"
                        elif new_path.is_dir():
                            status_msg = None
                            # Store current selection before moving down
                            last_selected[path] = selected
                            if is_allowed(new_path, allowed_roots):
                                path = new_path.resolve()
                                selected = last_selected.get(path, 0)
                                offset = 0
                                preview_lines = None
                                preview_file = None
                        else:
                            # File selected: open with configured launcher and return to browser
                            stdscr, status_msg = launch_external_app(stdscr, default_cmd_template, new_path)
            elif key in (curses.KEY_BACKSPACE, 127):
                status_msg = None
                if path != Path("/"):
                    path, selected, offset, preview_lines, preview_file = navigate_up(
                        path, selected, last_selected, allowed_roots
                    )
            elif key == ord('l'):
                if path != Path("/"):
                    # Enter list mode: build recursive BMS file list for current directory
                    bms_list = collect_bms_files(path)
                    if bms_list:
                        list_mode = True
                        selected = 0
                        offset = 0

        # ------------------------------------------------------------------
        # Rebuild entries if the directory changed during key handling
        # ------------------------------------------------------------------
        if path != old_path and not list_mode:
            entries, err = build_entries(path, allowed_roots)
            if err:
                status_msg = err
            # Adjust selection and offset to stay within bounds
            if selected >= len(entries):
                selected = max(0, len(entries) - 1)
            if offset > selected:
                offset = selected
            elif selected >= offset + max_entry_rows:
                offset = selected - max_entry_rows + 1

        # ------------------------------------------------------------------
        # Load more entries from the pending queue when scrolling down.
        # This implements a simple lazy‑loading mechanism.
        # ------------------------------------------------------------------
        # (No longer needed – all entries are kept in memory.)

        # ------------------------------------------------------------------
        # Refresh the screen after all updates
        # ------------------------------------------------------------------
        stdscr.refresh()

# ----------------------------------------------------------------------
if __name__ == "__main__":
    curses.wrapper(main)
