import curses
try:
    from player.key_listener import start_key_listener, get_key_events
    KEY_LISTENER_AVAILABLE = True
except ImportError:
    start_key_listener = None
    get_key_events = None
    KEY_LISTENER_AVAILABLE = False
from constants import get_key_names
from ui.factory import get_renderer

def make_on_update(stdscr, player, key_to_lane, opts, lane_chars):
    """Create an update callback for the player.

    Parameters:
        stdscr: curses window
        player: Player instance
        key_to_lane: mapping of input keys to lanes
        opts: dataclass Options(options.py)
        lane_chars: list/dict of characters representing notes per lane
    """
    mode = player.chart.get('mode', '7K').upper()
    key_names = get_key_names(mode, opts.scratch_side)

    renderer = get_renderer(opts.display_mode, mode, opts.judgement_y)

    def on_update(current_time, events, event_index, initial_bpm, resolution, auto_play):
        use_pynput = opts.use_pynput and KEY_LISTENER_AVAILABLE
        if use_pynput and not getattr(on_update, "_listener_started", False):
            if start_key_listener:
                start_key_listener()
            on_update._listener_started = True

        if not renderer:
            return

        try:
            stdscr.erase()
            renderer.render(
                stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play,
                opts, key_names, lane_chars, key_to_lane, use_pynput, get_key_events
            )
            stdscr.refresh()
        except curses.error:
            pass

    return on_update

