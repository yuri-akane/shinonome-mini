import tomllib
from pathlib import Path

# Global configuration variables
#show_measure_lines = True

# Channel to lane mapping (左スクラッチ: デフォルト)
# main.py の load_scratch_side() によって実行時に上書きされる場合がある
# CHANNEL_TO_LANE = {
#     "16": 0,   # scratch (1P)
#     "17": 0,   # foot pedal (1P)
#     "11": 1,
#     "12": 2,
#     "13": 3,
#     "14": 4,
#     "15": 5,
#     "18": 6,
#     "19": 7,
#     "21": 8,   # scratch (2P)
#     "22": 9,
#     "23": 10,
#     "24": 11,
#     "25": 12,
#     "28": 13,
#     "29": 14,
#     "26": 15,  # right scratch (2P)
#     "27": 15   # right foot pedal (2P)
# }

# def update_channel_to_lane(new_mapping: dict):
#     """main.py から呼び出して CHANNEL_TO_LANE を更新する"""
#     global CHANNEL_TO_LANE
#     CHANNEL_TO_LANE = new_mapping

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

def load_key_config(settings_path: str = "settings.toml", is_dp: bool = False) -> dict:
    """Load the custom key configuration from settings.toml.
    Returns a dict mapping integer key codes to lane indices.
    scratch_side に応じてスクラッチキーのレーン割り当てを変更する。
    """
    is_right = (scratch_side == "right") and not is_dp
    default_map = DEFAULT_KEY_TO_LANE_RIGHT if is_right else DEFAULT_KEY_TO_LANE_LEFT
    scratch_lane = 7 if is_right else 0

    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        return default_map.copy()

    try:
        with config_file.open('rb') as f:
            data = tomllib.load(f)
        keys_cfg = data.get('keys', {})
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
            # 右スクラッチ時: settings.tomlのlane0~lane6をインデックス0~6にマッピング
            for i in range(7):
                key_str = keys_cfg.get(f'lane{i}')
                if key_str and len(key_str) == 1:
                    new_map[ord(key_str)] = i
        else:
            # 左スクラッチ時: settings.tomlのlane0~lane6をインデックス1~7にマッピング
            for i in range(7):
                key_str = keys_cfg.get(f'lane{i}')
                if key_str and len(key_str) == 1:
                    new_map[ord(key_str)] = i + 1

        # 2P Keys (lane7 ~ lane13 mapped to index 8 ~ 14)
        for i in range(7, 14):
            key_str = keys_cfg.get(f'lane{i}')
            if key_str and len(key_str) == 1:
                new_map[ord(key_str)] = i + 1

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
    except Exception:
        return default_map.copy()

quit_key_name = "esc"

def load_quit_key(settings_path: str = "settings.toml") -> int:
    """Load the quit key configuration from settings.toml.
    Returns the integer key code. Supports single character strings and common names like "esc".
    """
    global quit_key_name
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        # Default to ESC if config missing
        quit_key_name = "esc"
        return 27
    with config_file.open('rb') as f:
        data = tomllib.load(f)
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

def load_scratch_side(settings_path: str = "settings.toml") -> str:
    """settings.toml の [scratch] side を読み込む。
    SP時のスクラッチ位置を "left" または "right" で返す。
    """
    #global scratch_side
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        scratch_side = "left"
        return scratch_side
    try:
        with config_file.open('rb') as f:
            data = tomllib.load(f)
        scratch_cfg = data.get('scratch', {})
        side = scratch_cfg.get('side', 'left').lower()
        scratch_side = side if side in ('left', 'right') else 'left'
    except Exception:
        scratch_side = "left"
    return scratch_side

# Auto Scratch handling
#auto_scratch: bool = False

def load_auto_scratch(settings_path: str = "settings.toml") -> bool:
    """Load the auto_scratch flag from settings.toml's [play_options] section.
    Returns the boolean value and updates the module-level auto_scratch variable.
    """
    #global auto_scratch
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        auto_scratch = False
        return auto_scratch
    try:
        with config_file.open('rb') as f:
            data = tomllib.load(f)
        play_opts = data.get('play_options', {})
        auto_scratch = play_opts.get('auto_scratch', False)
    except Exception:
        auto_scratch = False
    return auto_scratch

def load_judgement_config(settings_path: str = "settings.toml") -> tuple[int, int]:
    """Load judgement_y and judgement_offset_ms from settings.toml's [judgement] section.
    Returns a tuple (judgement_y, judgement_offset_ms)."""
    #global judgement_y_config, judgement_offset_ms_config
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        return 16, 0
    try:
        with config_file.open('rb') as f:
            data = tomllib.load(f)
        judg_cfg = data.get('judgement', {})
        judgement_y_config = judg_cfg.get('judgement_y', 16)
        judgement_offset_ms_config = judg_cfg.get('judgement_offset_ms', 0)
    except Exception:
        judgement_y_config = 16
        judgement_offset_ms_config = 0
    return judgement_y_config, judgement_offset_ms_config

def load_show_measure_lines(settings_path: str = "settings.toml") -> bool:
    """settings.toml の [play_options] show_measure_lines を読み込む。"""
    #global show_measure_lines
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        show_measure_lines = True
        return show_measure_lines
    try:
        with config_file.open('rb') as f:
            data = tomllib.load(f)
        play_opts = data.get('play_options', {})
        show_measure_lines = play_opts.get('show_measure_lines', True)
    except Exception:
        show_measure_lines = True
    return show_measure_lines

