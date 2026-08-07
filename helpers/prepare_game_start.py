def prepare_game_start(player, opt_scratch_side, channel_to_lane, lane_chars, KEY_TO_LANE,
                       judgement_y_config, judgement_offset_ms_config, opt_autoscratch,
                       opt_hard, opt_easy, opt_solid, opt_show_measure_lines,
                       opt_show_ln_end_head, opt_hispeed, speedup_code, speeddown_code,
                       play_opts, ui_mirror, ui_random):
    """
    Prepare game start configuration based on current options.
    This function mirrors the logic that was previously embedded in main().
    It returns a dictionary of settings to be passed to make_on_update and
    also updates the player instance with mode flags.
    """
    # Determine scratch lanes
    if player.chart.get('mode', 'SP') == 'DP':
        max_lane = 15
    else:
        max_lane = 7

    if player.chart.get('mode', 'SP') == 'DP':
        scratch_lanes = {0, max_lane}
    else:
        scratch_lanes = {7} if opt_scratch_side == "right" else {0}

    key_lanes = [i for i in range(max_lane + 1) if i not in scratch_lanes]

    # Rebuild base channel_to_lane mapping based on scratch side and mode
    from constants import CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT, LANE_CHARS_LEFT, LANE_CHARS_RIGHT
    if player.chart.get('mode', 'SP') == 'DP':
        # 1P側は左側に配置するため、LEFTマップを使用
        base_map = CHANNEL_TO_LANE_LEFT.copy()
    else:
        base_map = CHANNEL_TO_LANE_RIGHT.copy() if opt_scratch_side == "right" else CHANNEL_TO_LANE_LEFT.copy()

    # Apply lane map for mirror/random
    lane_map = {}
    import random
    if ui_random:
        if player.chart.get('mode', 'SP') == 'DP':
            lanes_1p = [lane for lane in key_lanes if 1 <= lane <= 7]
            lanes_2p = [lane for lane in key_lanes if 8 <= lane <= 14]
            shuffled_1p = lanes_1p[:]
            shuffled_2p = lanes_2p[:]
            random.shuffle(shuffled_1p)
            random.shuffle(shuffled_2p)
            lane_map = dict(zip(lanes_1p, shuffled_1p))
            lane_map.update(dict(zip(lanes_2p, shuffled_2p)))
        else:
            shuffled = key_lanes[:]
            random.shuffle(shuffled)
            lane_map = dict(zip(key_lanes, shuffled))
    elif ui_mirror:
        if player.chart.get('mode', 'SP') == 'DP':
            lane_map = {lane: (max_lane // 2 + 1 - lane) if lane <= (max_lane // 2)
                        else (max_lane + max_lane // 2 - lane) for lane in key_lanes}
        else:
            if opt_scratch_side == "right":
                lane_map = {lane: (max_lane - 1 - lane) for lane in key_lanes}
            else:
                lane_map = {lane: (max_lane + 1 - lane) for lane in key_lanes}

    # Apply lane map to base channel mapping
    if lane_map:
        channel_to_lane = {ch: lane_map.get(lane, lane) for ch, lane in base_map.items()}
    else:
        channel_to_lane = base_map

    # Determine lane_chars based on scratch side (SP mode) or keep default for DP
    if player.chart.get('mode', 'SP') == 'DP':
        # 1P側は左側なのでLEFTの文字列を使用
        lane_chars = LANE_CHARS_LEFT
    else:
        lane_chars = LANE_CHARS_RIGHT if opt_scratch_side == "right" else LANE_CHARS_LEFT

    # Update player flags and mapping
    player.auto_scratch = opt_autoscratch
    player.hard_mode = opt_hard
    player.easy_mode = opt_easy and not opt_hard
    player.solid_gauge = opt_solid
    player.show_measure_lines = opt_show_measure_lines
    player.judgement_offset_ms = judgement_offset_ms_config
    # Update the player's channel mapping to reflect lane changes
    player.channel_to_lane = channel_to_lane

    # Recompute keyboard-to-lane mapping based on scratch side and mode
    is_dp = (player.chart.get('mode', 'SP') == 'DP')
    from config import load_key_config
    KEY_TO_LANE = load_key_config(opt_scratch_side, is_dp=is_dp)

    # Prepare modifier keys
    from config import load_modifier_keys, load_use_pynput
    mod_keys = load_modifier_keys()
    if 'shift_r' not in mod_keys:
        mod_keys['shift_r'] = 7

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
