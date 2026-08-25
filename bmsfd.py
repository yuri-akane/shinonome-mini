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
import sys
import subprocess
from collections import defaultdict

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

def parse_song_file(path: Path) -> dict:
    """
    Read a plain‑text song file and extract the following keys if present:
        #TITLE, #SUBTITLE, #ARTIST, #SUBARTIST, #GENRE, #PLAYLEVEL, #BPM,
        #DIFFICULTY, #LEVEL
    The value is everything after the first space on the line.
    This function now opens files with CP932 decoding while ignoring any
    undecodable bytes so that CP932 (shift‑JIS) encoded files containing
    non‑ASCII characters do not raise an exception.
    """
    props = {}
    try:
        # Open with CP932 and ignore undecodable bytes
        with path.open("r", encoding="cp932", errors="ignore") as f:
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
def load_settings() -> set[Path]:
    """
    Load allowed root directories from settings.toml in the repository root.
    If the file or key is missing, all paths are considered allowed.
    Returns a set of absolute Path objects.
    """
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib

    repo_root = Path(__file__).resolve().parent
    settings_file = repo_root / "settings.toml"
    if not settings_file.exists():
        return set()  # allow all

    try:
        with settings_file.open("rb") as f:
            data = tomllib.load(f)
    except Exception:  # pragma: no cover
        return set()

    roots = data.get("allowed_roots", [])
    allowed = set()
    for r in roots:
        p = (repo_root / r).resolve()
        allowed.add(p)
    return allowed

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
def open_file_with_cnnm(stdscr, path: Path) -> curses.window:
    """
    Temporarily leave curses mode to run bms on the given file.
    After bms exits, re‑enter curses and restore the terminal state.
    Returns the new stdscr window object for continued use.
    """
    # End curses so that nano can take over the terminal
    curses.endwin()
    try:
        subprocess.run(["python3", "main.py", str(path)])
    finally:
        # Reinitialize curses after nano exits
        new_stdscr = curses.initscr()
        curses.curs_set(0)
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
def main(stdscr):
    # --------------------------------------------------------------
    # 1. Initialise state
    # --------------------------------------------------------------
    allowed_roots = load_settings()

    config_msg = None
    if not allowed_roots:
        # No settings found; fall back to current directory and warn user.
        allowed_roots = {Path.cwd().resolve()}
        config_msg = ("No allowed_roots found in settings.toml; "
                      "using current directory. Please configure settings.")

    # Determine initial path: if a command‑line argument is given, use it;
    # otherwise show a virtual root that lists all allowed roots.
    if len(sys.argv) > 1:
        path = Path(sys.argv[1]).expanduser().resolve()
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

    # ------------------------------------------------------------------
    # State for list mode toggle
    # ------------------------------------------------------------------
    list_mode = False          # whether we are showing the recursive BMS list
    bms_list: list[Path] | None = None  # cached list of files when in list mode

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

        # Show configuration warning if present
        if config_msg:
            try:
                stdscr.addnstr(1, 0, config_msg, w-1, curses.A_DIM)
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
        #   1 (optional): config message
        #   2/3       : blank line(s) separator
        #   preview area
        #   entries start here
        #   last row   : help line
        # ------------------------------------------------------------------
        top_offset = 0
        if path == Path("/"):
            header_row = 0
        else:
            header_row = 0

        msg_rows = 1 if config_msg else 0
        prop_start_row = header_row + msg_rows + 1  # one blank line after header/message
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
            if path == Path("/"):
                # Virtual root: show all allowed roots as entries
                raw_entries = sorted(allowed_roots, key=lambda p: p.name.lower())
                entries = [p for p in raw_entries]
            else:
                raw_entries = [
                    p for p in path.iterdir()
                    if p.is_dir() or p.suffix.lower() in SUPPORTED_EXTENSIONS
                ]

                # Populate placeholder properties for each file (no‑op yet)
                for p in raw_entries:
                    if not p.is_dir():
                        _ = file_props[p]  # creates the default dict entry

                entries = [Path("..")] + sorted(
                    raw_entries,
                    key=lambda p: (not p.is_dir(), p.name.lower())
                )

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
        # Show preview if the user has requested it with Space and we have room
        # ------------------------------------------------------------------
        if preview_lines is not None and prop_rows > 0:
            max_prop_rows = prop_rows   # use the allocated property area

            for i, line in enumerate(preview_lines):
                if i >= max_prop_rows:
                    break
                try:
                    stdscr.addnstr(prop_start_row + i,
                                   0,
                                   f"{line}",
                                   w-1,
                                   curses.A_BOLD)
                except curses.error:
                    # ignore lines that don't fit (e.g., very small terminal)
                    pass

        # ------------------------------------------------------------------
        # Help / key‑function legend at the bottom line (row h‑1)
        # ------------------------------------------------------------------
        help_msg = "Esc: quit | Backspace/..: up | Enter: open dir / play file | L: list all BMS recursively"
        try:
            stdscr.addnstr(h - 1, 0, help_msg, w-1, curses.A_DIM)
        except curses.error:
            # terminal too small to show the help line; ignore
            pass

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
                    stdscr = open_file_with_cnnm(stdscr, chosen)
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
                    if is_allowed(new_path, allowed_roots):
                        last_selected[path] = selected
                        path = new_path
                        selected = last_selected.get(path, 0)
                        offset = 0
                        preview_lines = None          # clear any existing preview
                        preview_file = None
                else:
                    if chosen.name == "..":
                        # Store current selection before moving up
                        last_selected[path] = selected
                        new_path = path.parent
                        if is_allowed(new_path, allowed_roots):
                            path = new_path
                            selected = last_selected.get(path, 0)
                            offset = 0
                            preview_lines = None
                            preview_file = None
                        else:
                            # Cannot move up; show virtual root instead
                            path = Path("/")
                            selected = 0
                            offset = 0
                            preview_lines = None
                            preview_file = None
                    else:
                        new_path = path / chosen
                        if new_path.is_dir():
                            # Store current selection before moving down
                            last_selected[path] = selected
                            if is_allowed(new_path, allowed_roots):
                                path = new_path.resolve()
                                selected = last_selected.get(path, 0)
                                offset = 0
                                preview_lines = None
                                preview_file = None
                        else:
                            # File selected: open with cnnm and return to browser
                            stdscr = open_file_with_cnnm(stdscr, new_path)
            elif key in (curses.KEY_BACKSPACE, 127):
                if path != Path("/"):
                    # same as selecting ".."
                    last_selected[path] = selected
                    new_path = path.parent
                    if is_allowed(new_path, allowed_roots):
                        path = new_path
                        selected = last_selected.get(path, 0)
                        offset = 0
                        preview_lines = None
                        preview_file = None
                    else:
                        # Cannot move up; show virtual root instead
                        path = Path("/")
                        selected = 0
                        offset = 0
                        preview_lines = None
                        preview_file = None
            elif key == ord('l'):
                # Enter list mode: build recursive BMS file list for current directory
                bms_list = collect_bms_files(path)
                if bms_list:
                    list_mode = True
                    selected = 0
                    offset = 0

        # ------------------------------------------------------------------
        # Rebuild entries if the directory changed during key handling
        # ------------------------------------------------------------------
        if path != old_path:
            if list_mode:
                # In list mode we keep the same bms_list; no rebuild needed
                pass
            else:
                if path == Path("/"):
                    raw_entries = sorted(allowed_roots, key=lambda p: p.name.lower())
                    entries = [p for p in raw_entries]
                else:
                    raw_entries = [
                        p for p in path.iterdir()
                        if p.is_dir() or p.suffix.lower() in SUPPORTED_EXTENSIONS
                    ]
                    for p in raw_entries:
                        if not p.is_dir():
                            _ = file_props[p]
                    entries = [Path("..")] + sorted(
                        raw_entries,
                        key=lambda p: (not p.is_dir(), p.name.lower())
                    )
                # Adjust selection and offset to stay within bounds
                if selected >= len(entries):
                    selected = max(0, len(entries) - 1)
                if offset > selected:
                    offset = selected
                elif selected >= offset + max_entry_rows:
                    offset = selected - max_entry_rows + 1

        # ------------------------------------------------------------------
        # Update preview automatically when the cursor moves onto a file or directory
        # ------------------------------------------------------------------
        sel_entry = entries[selected] if entries else None
        if path != Path("/") and sel_entry:
            if not list_mode:
                if not sel_entry.is_dir() and sel_entry.suffix.lower() in SUPPORTED_EXTENSIONS:
                    try:
                        props = parse_song_file(path / sel_entry)
                        preview_lines = []
                        # Display order requested by the user.
                        order = ["genre", "title", "subtitle", "artist",
                                 "subartist", "playlevel", "bpm"]
                        for key in order:
                            val = props.get(key, "")
                            if val:
                                preview_lines.append(f"{key.title()}: {val}")
                            else:
                                preview_lines.append("")
                    except Exception:
                        preview_lines = None
                elif sel_entry.is_dir():
                    try:
                        bms_files = sorted(
                            (p for p in (path / sel_entry).iterdir()
                             if p.suffix.lower() in SUPPORTED_EXTENSIONS),
                            key=lambda p: p.name.lower()
                        )
                        preview_lines = [f"{p.name}" for p in bms_files]
                    except Exception:
                        preview_lines = None
            else:
                # In list mode, sel_entry is a file path
                try:
                    props = parse_song_file(sel_entry)
                    preview_lines = []
                    order = ["genre", "title", "subtitle", "artist",
                             "subartist", "playlevel", "bpm"]
                    for key in order:
                        val = props.get(key, "")
                        if val:
                            preview_lines.append(f"{key.title()}: {val}")
                        else:
                            preview_lines.append("")
                except Exception:
                    preview_lines = None
        else:
            preview_lines = None

        # After handling keys, redraw preview if needed (in case Space was pressed)
        if preview_lines is not None and prop_rows > 0:
            max_prop_rows = prop_rows
            for i, line in enumerate(preview_lines):
                if i >= max_prop_rows:
                    break
                try:
                    stdscr.addnstr(prop_start_row + i,
                                   0,
                                   f"{line}",
                                   w-1,
                                   curses.A_BOLD)
                except curses.error:
                    pass

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
