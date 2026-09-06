import curses
import config
try:
    from key_listener import start_key_listener, get_key_events
    KEY_LISTENER_AVAILABLE = True
except ImportError:
    start_key_listener = None
    get_key_events = None
    KEY_LISTENER_AVAILABLE = False
from constants import get_key_names
from ui.factory import get_renderer


def make_on_update(stdscr, player, quit_key_code, key_to_lane, judgement_y_config, settings, lane_chars, display_mode="mini"):
    """Create an update callback for the player.

    Parameters:
        stdscr: curses window
        player: Player instance
        quit_key_code: key code to quit
        key_to_lane: mapping of input keys to lanes
        judgement_y_config: y-position for judgement line
        settings: mutable settings dict (e.g., hispeed)
        lane_chars: list/dict of characters representing notes per lane
        display_mode: 'mini', 'tiny', 'none', or 'soundonly'
    """
    def _key_code(k):
        if isinstance(k, str):
            uk = k.upper()
            if uk == 'KEY_UP':
                return curses.KEY_UP
            if uk == 'KEY_DOWN':
                return curses.KEY_DOWN
            return ord(k)
        return k

    mode = player.chart.get('mode', '7K').upper()
    key_names = get_key_names(mode, settings.get('opt_scratch_side', 'left'))
    speedup_keycode   = _key_code(settings.get('speedup_key', '+'))
    speeddown_keycode = _key_code(settings.get('speeddown_key', '-'))

    renderer = get_renderer(display_mode, mode, judgement_y_config)

    def on_update(current_time, events, event_index, initial_bpm, resolution, auto_play):
        use_pynput = settings.get('use_pynput', True) and KEY_LISTENER_AVAILABLE
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
                settings, key_names, lane_chars, quit_key_code, key_to_lane,
                speedup_keycode, speeddown_keycode, use_pynput, get_key_events
            )
            stdscr.refresh()
        except curses.error:
            pass

    return on_update

