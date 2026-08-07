import curses
from config import (
    load_scratch_side,
    load_key_config,
    load_quit_key,
    load_judgement_config,
    _load_toml,
)
import config
from constants import (
    CHANNEL_TO_LANE_LEFT,
    CHANNEL_TO_LANE_RIGHT,
    LANE_CHARS_LEFT,
    LANE_CHARS_RIGHT,
)

def load_initial_settings(player):
    """
    Load configuration and initialize player settings.

    Parameters
    ----------
    player : Player
        The player instance to configure.  Its ``channel_to_lane`` attribute will be
        updated in place.

    Returns
    -------
    dict
        A dictionary containing all the options that were read from disk or
        derived from defaults.
    """
    # Scratch side handling (SP only)
    opt_scratch_side = load_scratch_side()

    # Determine lane mapping based on mode and scratch side
    if player.chart and player.chart.get('mode', 'SP') == 'SP' and opt_scratch_side == "right":
        channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
        lane_chars = LANE_CHARS_RIGHT.copy()
    else:
        channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        lane_chars = LANE_CHARS_LEFT.copy()

    # Sync player mapping
    is_dp = (player.chart.get('mode', 'SP') == 'DP') if player.chart else False
    KEY_TO_LANE = load_key_config(opt_scratch_side, is_dp=is_dp)
    quit_key_code = load_quit_key()
    judgement_y_config, judgement_offset_ms_config = load_judgement_config()

    # Load TOML configuration (play options and hispeed keys)
    try:
        data = _load_toml()
        play_opts = data.get('play_options', {})
        opt_autoplay = play_opts.get('autoplay', False)
        opt_mirror = play_opts.get('mirror', False)
        opt_random = play_opts.get('random', False)
        opt_easy = play_opts.get('easy_mode', False)
        opt_hard = play_opts.get('hard_gauge', False)
        opt_solid = play_opts.get('solid_gauge', False)
        opt_show_measure_lines = play_opts.get('show_measure_lines', True)
        opt_show_ln_end_head = play_opts.get('show_ln_end_head', True)
        opt_hispeed = play_opts.get('hispeed', 1.0)
        opt_autoscratch = play_opts.get('auto_scratch', False)

        # Configurable hispeed key bindings
        speedup_key = data.get('speedup_key', 'KEY_UP')
        speeddown_key = data.get('speeddown_key', 'KEY_DOWN')

        def _key_code(k):
            if isinstance(k, str):
                uk = k.upper()
                if uk == 'KEY_UP':
                    return curses.KEY_UP
                if uk == 'KEY_DOWN':
                    return curses.KEY_DOWN
                return ord(k)
            return k

        speedup_code = _key_code(speedup_key)
        speeddown_code = _key_code(speeddown_key)

    except Exception:
        # Fallback defaults in case of any error reading the config
        opt_autoplay = True
        opt_mirror = False
        opt_random = False
        opt_easy = False
        opt_hard = False
        opt_solid = False
        opt_show_measure_lines = True
        opt_hispeed = 1.0
        opt_scratch_side = "left"
        opt_autoscratch = False
        speedup_code = curses.KEY_UP
        speeddown_code = curses.KEY_DOWN

    # Sync player mapping after determining channel_to_lane
    player.channel_to_lane = channel_to_lane

    return {
        'opt_scratch_side': opt_scratch_side,
        'channel_to_lane': channel_to_lane,
        'lane_chars': lane_chars,
        'is_dp': is_dp,
        'KEY_TO_LANE': KEY_TO_LANE,
        'quit_key_code': quit_key_code,
        'judgement_y_config': judgement_y_config,
        'judgement_offset_ms_config': judgement_offset_ms_config,
        'opt_autoplay': opt_autoplay,
        'opt_mirror': opt_mirror,
        'opt_random': opt_random,
        'opt_easy': opt_easy,
        'opt_hard': opt_hard,
        'opt_solid': opt_solid,
        'opt_show_measure_lines': opt_show_measure_lines,
        'opt_show_ln_end_head': opt_show_ln_end_head,
        'opt_hispeed': opt_hispeed,
        'opt_autoscratch': opt_autoscratch,
        'speedup_code': speedup_code,
        'speeddown_code': speeddown_code,
        'play_opts': play_opts,  # expose for later use
    }
