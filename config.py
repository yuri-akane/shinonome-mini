import tomllib
from pathlib import Path

def _load_toml(settings_path: str = "settings.toml") -> dict:
    """Load settings.toml and return its content as a dict.

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        return {}
    try:
        with config_file.open('rb') as f:
            return tomllib.load(f)
    except Exception:
        return {}


DEFAULT_KEY_TO_LANE_LEFT = {
    # Player 1 (左スクラッチ)
    ord(' '): 0,  # Space: Scratch (1P)
    ord('a'): 0,  # a: Scratch (1P)
    ord('z'): 1,
    ord('s'): 2,
    ord('x'): 3,
    ord('d'): 4,
    ord('c'): 5,
    ord('f'): 6,
    ord('v'): 7,
    # Player 2
    ord('j'): 8,
    ord('k'): 9,
    ord('l'): 10,
    ord(';'): 11,
    ord("'"): 12,
    ord('n'): 13,
    ord('m'): 14,
    ord(','): 15,
}

DEFAULT_KEY_TO_LANE_RIGHT = {
    # Player 1 (右スクラッチ: 鍵盤が0~6、スクラッチが7)
    ord('z'): 0,
    ord('s'): 1,
    ord('x'): 2,
    ord('d'): 3,
    ord('c'): 4,
    ord('f'): 5,
    ord('v'): 6,
    ord(' '): 7,  # Space: Scratch (1P) → 右端
    ord('a'): 7,  # a: Scratch (1P) → 右端
    # Player 2
    ord('j'): 8,
    ord('k'): 9,
    ord('l'): 10,
    ord(';'): 11,
    ord("'"): 12,
    ord('n'): 13,
    ord('m'): 14,
    ord(','): 15,
}

def load_key_config(scratch_side, is_dp: bool = False) -> dict:
    """Load the custom key configuration from settings.toml.
    Returns a dict mapping integer key codes to lane indices.
    scratch_side に応じてスクラッチキーのレーン割り当てを変更する。
    """
    is_right = (scratch_side == "right") and not is_dp
    default_map = DEFAULT_KEY_TO_LANE_RIGHT if is_right else DEFAULT_KEY_TO_LANE_LEFT
    scratch_lane = 7 if is_right else 0

    config_data = _load_toml()
    if not config_data:
        return default_map.copy()
    keys_cfg = config_data.get('keys', {})
    if not keys_cfg:
        return default_map.copy()

    new_map = {}

    # 1P Scratch - side aware (scratch_SP_left / scratch_SP_right / scratch_DP_left)
    if is_dp:
        ls_key = 'scratch_DP_left'
    else:
        ls_key = 'scratch_SP_right' if is_right else 'scratch_SP_left'
    ls = keys_cfg.get(ls_key, ["a", " ", "\t"])
    if isinstance(ls, str):
        ls = [ls]
    for key_str in ls:
        if len(key_str) == 1:
            new_map[ord(key_str)] = scratch_lane
        elif key_str == "\t":
            new_map[9] = scratch_lane # ASCII Tab

    # 1P Keys
    if is_right:
        # 右スクラッチ時: settings.tomlのlane0~lane6をインデックス0~6にマッピング（単一キーまたは複数キー）
        for i in range(7):
            lane_val = keys_cfg.get(f'lane{i}')
            # Normalize to list
            if isinstance(lane_val, str):
                lane_keys = [lane_val]
            elif isinstance(lane_val, list):
                lane_keys = lane_val
            else:
                lane_keys = []
            for key_str in lane_keys:
                if not isinstance(key_str, str):
                    continue
                if len(key_str) == 1:
                    new_map[ord(key_str)] = i
                elif key_str == "\t":
                    new_map[9] = i  # Tab key

    else:
        # 左スクラッチ時: settings.tomlのlane0~lane6をインデックス1~7にマッピング（単一キーまたは複数キー）
        for i in range(7):
            lane_val = keys_cfg.get(f'lane{i}')
            if isinstance(lane_val, str):
                lane_keys = [lane_val]
            elif isinstance(lane_val, list):
                lane_keys = lane_val
            else:
                lane_keys = []
            for key_str in lane_keys:
                if not isinstance(key_str, str):
                    continue
                if len(key_str) == 1:
                    new_map[ord(key_str)] = i + 1
                elif key_str == "\t":
                    new_map[9] = i + 1


    # 2P Keys (lane7 ~ lane13 mapped to index 8 ~ 14) – support multiple keys per lane
    for i in range(7, 14):
        lane_val = keys_cfg.get(f'lane{i}')
        if isinstance(lane_val, str):
            lane_keys = [lane_val]
        elif isinstance(lane_val, list):
            lane_keys = lane_val
        else:
            lane_keys = []
        for key_str in lane_keys:
            if not isinstance(key_str, str):
                continue
            if len(key_str) == 1:
                new_map[ord(key_str)] = i + 1
            elif key_str == "\t":
                new_map[9] = i + 1


    # 2P Scratch (scratch_DP_right) - can be a single key or a list
    rs = keys_cfg.get('scratch_DP_right', ["", "\n"])
    if isinstance(rs, str):
        rs = [rs]
    for key_str in rs:
        if len(key_str) == 1:
            new_map[ord(key_str)] = 15
        elif key_str == "\n":
            new_map[10] = 15 # ASCII LF / Enter
            new_map[13] = 15 # ASCII CR / Enter

    return new_map if new_map else default_map.copy()


quit_key_name = "esc"

def load_quit_key() -> int:
    """Load the quit key configuration from settings.toml.
    Returns the integer key code. Supports single character strings and common names like "esc".
    """
    global quit_key_name
    data = _load_toml()
    quit_cfg = data.get('quit', {})
    key_val = quit_cfg.get('key', 'esc')
    if isinstance(key_val, str):
        key_val = key_val.lower()
        if key_val == 'esc':
            quit_key_name = "esc"
            return 27
        # If it's a single character, return its ord
        if len(key_val) == 1:
            quit_key_name = key_val
            return ord(key_val)
    # Fallback
    quit_key_name = "esc"
    return 27

def load_modifier_keys() -> dict:
    """Load modifier key mappings from settings.toml.

    The [modifiers] section can define left/right modifiers, e.g.:
        shift_l = 0   # 左 Shift → lane 0
        shift_r = 7   # 右 Shift → lane 7
        ctrl_l  = 1
        ctrl_r  = 8
        alt_l   = 2
        alt_r   = 9
    The function returns a dict mapping the *pynput* key names ("shift", "shift_r",
    "ctrl", "ctrl_r", "alt", "alt_r") to lane indices.  Left modifiers are also
    accessible via the generic names "shift", "ctrl", "alt".  If no mapping is defined,
    it falls back to the legacy behaviour: map generic "shift" to lane 0 based on the
    left‑scratch configuration.
    """
    data = _load_toml()
    mod_cfg = data.get('modifiers', {})
    result: dict[str, int] = {}
    # Process explicit left/right mappings
    for name, lane in mod_cfg.items():
        if not isinstance(lane, int):
            continue
        name_lc = name.lower()
        if name_lc.endswith('_l'):
            base = name_lc[:-2]
            result[base] = lane  # generic left name (e.g. "shift")
        elif name_lc.endswith('_r'):
            base = name_lc[:-2]
            result[f"{base}_r"] = lane
        else:
            result[name_lc] = lane
    # Legacy fallback when no mapping at all
    if not result:
        key_cfg = data.get('keys', {})
        left_scratch = key_cfg.get('scratch_SP_left', [])
        if isinstance(left_scratch, str):
            left_scratch = [left_scratch]
        for k in left_scratch:
            if isinstance(k, str) and k.lower() == 'shift':
                result['shift'] = 0
                break
    return result

def load_use_pynput() -> bool:
    """Load use_pynput flag from settings.toml. Defaults to True."""
    data = _load_toml()
    mod_cfg = data.get('modifiers', {})
    return mod_cfg.get('use_pynput', True)

def load_scratch_side() -> str:
    """settings.toml の [scratch] side を読み込む。
    SP時のスクラッチ位置を "left" または "right" で返す。
    """
    data = _load_toml()
    if not data:
        return "left"
    scratch_cfg = data.get('scratch', {})
    side = scratch_cfg.get('side', 'left').lower()
    return side if side in ('left', 'right') else 'left'

# def load_auto_scratch() -> bool:
#     """Load the auto_scratch flag from settings.toml's [play_options] section.
#     Returns the boolean value and updates the module-level auto_scratch variable.
#     """
#     data = _load_toml()
#     if not data:
#         auto_scratch = False
#         return auto_scratch
#     play_opts = data.get('play_options', {})
#     auto_scratch = play_opts.get('auto_scratch', False)

def load_judgement_config() -> tuple[int, int]:
    """Load judgement_y and judgement_offset_ms from settings.toml's [judgement] section.
    Returns a tuple (judgement_y, judgement_offset_ms)."""
    data = _load_toml()
    if not data:
        return 16, 0
    judg_cfg = data.get('judgement', {})
    judgement_y_config = judg_cfg.get('judgement_y', 16)
    judgement_offset_ms_config = judg_cfg.get('judgement_offset_ms', 0)
    return judgement_y_config, judgement_offset_ms_config

# def load_show_measure_lines() -> bool:
#     """settings.toml の [play_options] show_measure_lines を読み込む。"""
#     data = _load_toml()
#     if not data:
#         show_measure_lines = True
#         return show_measure_lines
#     play_opts = data.get('play_options', {})
#     show_measure_lines = play_opts.get('show_measure_lines', True)

