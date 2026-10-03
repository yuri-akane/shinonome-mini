import random
from constants import get_channel_to_lane_map, get_lane_chars


def prepare_game_start(player, opts, channel_to_lane):
    """
    Prepare game start configuration based on current options.
    It returns a dictionary of settings to be passed to make_on_update and
    also updates the player instance with mode flags.
    """
    mode = player.chart.get('mode', '7K').upper()

    base_map = get_channel_to_lane_map(mode, opts.scratch_side)
    lane_chars = get_lane_chars(mode, opts.scratch_side, display_mode=opts.display_mode)

    if mode == '4K':
        lanes_1p = [0, 1, 2, 3]
        lanes_2p = []
    elif mode == '6K':
        lanes_1p = [0, 1, 2, 3, 4, 5]
        lanes_2p = []
    elif mode == '9K':
        lanes_1p = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        lanes_2p = []
    elif mode == '5K':
        if opts.scratch_side == "right":
            lanes_1p = [0, 1, 2, 3, 4]
        else:
            lanes_1p = [1, 2, 3, 4, 5]
        lanes_2p = []
    elif mode == '10K':
        lanes_1p = [1, 2, 3, 4, 5]
        lanes_2p = [6, 7, 8, 9, 10]
    elif mode == '7K':
        if opts.scratch_side == "right":
            lanes_1p = [0, 1, 2, 3, 4, 5, 6]
        else:
            lanes_1p = [1, 2, 3, 4, 5, 6, 7]
        lanes_2p = []
    else:  # 14K
        lanes_1p = [1, 2, 3, 4, 5, 6, 7]
        lanes_2p = [8, 9, 10, 11, 12, 13, 14]

    # Apply lane map for mirror/random
    lane_map = {}
    if opts.random:
        if lanes_1p:
            shuffled_1p = lanes_1p[:]
            random.shuffle(shuffled_1p)
            lane_map.update(dict(zip(lanes_1p, shuffled_1p)))
        if lanes_2p:
            shuffled_2p = lanes_2p[:]
            random.shuffle(shuffled_2p)
            lane_map.update(dict(zip(lanes_2p, shuffled_2p)))
    elif opts.mirror:
        if lanes_1p:
            lane_map.update(dict(zip(lanes_1p, reversed(lanes_1p))))
        if lanes_2p:
            lane_map.update(dict(zip(lanes_2p, reversed(lanes_2p))))

    # Apply lane map to base channel mapping
    if lane_map:
        channel_to_lane = {ch: lane_map.get(lane, lane) for ch, lane in base_map.items()}
    else:
        channel_to_lane = base_map

    # Update player flags and mapping
    #todo:なぜかここでplayerに直接値を設定する経路とoptsで渡す経路の2つがあるので要refactor
    player.auto_scratch = opts.autoscratch
    player.hard_mode = opts.hard
    player.easy_mode = opts.easy and not opts.hard
    player.solid_gauge = opts.solid
    player.show_measure_lines = opts.show_measure_lines
    player.judgement_offset_ms = opts.judgement_offset_ms
    player.note_display_offset_ms = getattr(opts, 'note_display_offset_ms', 0)
    player.channel_to_lane = channel_to_lane

    # Recompute keyboard-to-lane mapping based on scratch side and mode
    is_dp = (mode in ('10K', '14K'))
    KEY_TO_LANE = opts.load_key_config(opts.scratch_side, is_dp=is_dp, mode=mode)
    player.active_key_lanes = set(KEY_TO_LANE.values())

    # Prepare modifier keys
    #mod_keys = opts.load_modifier_keys(mode=mode, scratch_side=opts.scratch_side)

    return {
        'channel_to_lane': channel_to_lane,
        'lane_chars': lane_chars,
        'KEY_TO_LANE': KEY_TO_LANE,
    }
