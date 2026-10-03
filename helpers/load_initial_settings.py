from helpers.options import load_options
from constants import get_channel_to_lane_map, get_lane_chars

def load_initial_settings(player, args=None):
    """
    Load configuration and initialize player settings.

    Parameters
    ----------
    player : Player
        The player instance to configure.  Its ``channel_to_lane`` attribute will be
        updated in place.
    args : argparse.Namespace, optional
        Parsed CLI arguments.

    Returns
    -------
    dict
        A dictionary containing all the options that were read from disk or
        derived from defaults.
    """
    opts = load_options(args)

    # ゲームモード強制指定（CLIの --mode / --mode-hint）
    force_mode = opts.force_mode
    if force_mode and player.chart:
        player.chart['mode'] = force_mode
        player.chart['is_dp'] = (force_mode in ('10K', '14K'))

    mode = player.chart.get('mode', '7K').upper() if player.chart else '7K'
    is_dp = (mode in ('10K', '14K'))

    channel_to_lane = get_channel_to_lane_map(mode, opts.scratch_side)
    lane_chars = get_lane_chars(mode, opts.scratch_side)

    KEY_TO_LANE = opts.load_key_config(opts.scratch_side, is_dp=is_dp, mode=mode)

    # Sync player mapping
    player.channel_to_lane = channel_to_lane
    player.active_key_lanes = set(KEY_TO_LANE.values())

    return {
        'opts': opts,
        'channel_to_lane': channel_to_lane,
        'lane_chars': lane_chars,
        'is_dp': is_dp,
        'KEY_TO_LANE': KEY_TO_LANE
    }
