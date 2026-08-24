def prepare_game_start(player, opt_scratch_side, channel_to_lane, lane_chars, KEY_TO_LANE,
                       judgement_y_config, judgement_offset_ms_config, opt_autoscratch,
                       opt_hard, opt_easy, opt_solid, opt_show_measure_lines,
                       opt_show_ln_end_head, opt_hispeed, speedup_code, speeddown_code,
                       play_opts, ui_mirror, ui_random):
    """
    Prepare game start configuration based on current options.
    It returns a dictionary of settings to be passed to make_on_update and
    also updates the player instance with mode flags.
    """
    from constants import get_channel_to_lane_map, get_lane_chars
    import random

    mode = player.chart.get('mode', '7K').upper()

    base_map = get_channel_to_lane_map(mode, opt_scratch_side)
    lane_chars = get_lane_chars(mode, opt_scratch_side)

    if mode == '9K':
        lanes_1p = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        lanes_2p = []
    elif mode == '5K':
        if opt_scratch_side == "right":
            lanes_1p = [0, 1, 2, 3, 4]
        else:
            lanes_1p = [1, 2, 3, 4, 5]
        lanes_2p = []
    elif mode == '10K':
        lanes_1p = [1, 2, 3, 4, 5]
        lanes_2p = [6, 7, 8, 9, 10]
    elif mode == '7K':
        if opt_scratch_side == "right":
            lanes_1p = [0, 1, 2, 3, 4, 5, 6]
        else:
            lanes_1p = [1, 2, 3, 4, 5, 6, 7]
        lanes_2p = []
    else:  # 14K
        lanes_1p = [1, 2, 3, 4, 5, 6, 7]
        lanes_2p = [8, 9, 10, 11, 12, 13, 14]

    # Apply lane map for mirror/random
    lane_map = {}
    if ui_random:
        if lanes_1p:
            shuffled_1p = lanes_1p[:]
            random.shuffle(shuffled_1p)
            lane_map.update(dict(zip(lanes_1p, shuffled_1p)))
        if lanes_2p:
            shuffled_2p = lanes_2p[:]
            random.shuffle(shuffled_2p)
            lane_map.update(dict(zip(lanes_2p, shuffled_2p)))
    elif ui_mirror:
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
    player.auto_scratch = opt_autoscratch
    player.hard_mode = opt_hard
    player.easy_mode = opt_easy and not opt_hard
    player.solid_gauge = opt_solid
    player.show_measure_lines = opt_show_measure_lines
    player.judgement_offset_ms = judgement_offset_ms_config
    player.channel_to_lane = channel_to_lane

    # Recompute keyboard-to-lane mapping based on scratch side and mode
    from config import load_key_config
    is_dp = (mode in ('10K', '14K'))
    KEY_TO_LANE = load_key_config(opt_scratch_side, is_dp=is_dp, mode=mode)

    # Prepare modifier keys
    from config import load_modifier_keys, load_use_pynput
    mod_keys = load_modifier_keys(mode=mode, scratch_side=opt_scratch_side)

    opt_use_pynput = load_use_pynput()

    settings = {
        'hispeed': opt_hispeed,
        'opt_scratch_side': opt_scratch_side,
        'modifier_keys': mod_keys,
        'speedup_key': play_opts.get('speedup_key', 'KEY_UP'),
        'speeddown_key': play_opts.get('speeddown_key', 'KEY_DOWN'),
        'use_pynput': opt_use_pynput,
        'opt_solid': opt_solid,
        'show_ln_end_head': opt_show_ln_end_head
    }

    return {
        'channel_to_lane': channel_to_lane,
        'lane_chars': lane_chars,
        'KEY_TO_LANE': KEY_TO_LANE,
        'settings': settings
    }
