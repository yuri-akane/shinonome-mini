import tomllib
from pathlib import Path

# Channel to lane mapping (左スクラッチ: デフォルト)
# main.py の load_scratch_side() によって実行時に上書きされる場合がある
CHANNEL_TO_LANE = {
    "16": 0,   # scratch (1P)
    "17": 0,   # foot pedal (1P)
    "11": 1,
    "12": 2,
    "13": 3,
    "14": 4,
    "15": 5,
    "18": 6,
    "19": 7,
    "21": 8,   # scratch (2P)
    "22": 9,
    "23": 10,
    "24": 11,
    "25": 12,
    "28": 13,
    "29": 14,
    "26": 15,  # right scratch (2P)
    "27": 15   # right foot pedal (2P)
}

def update_channel_to_lane(new_mapping: dict):
    """main.py から呼び出して CHANNEL_TO_LANE を更新する"""
    global CHANNEL_TO_LANE
    CHANNEL_TO_LANE = new_mapping

def load_key_to_lane(settings_path: str = "settings.toml") -> dict[int, int]:
    """Load key-to-lane mapping from settings.toml.

    The settings file defines a [keys] table where each entry is either a list of
    characters (for scratch keys) or a single character string for normal lanes.
    This function converts those definitions into a dictionary mapping the *ord*
    value of each character to the lane index.
    """
    config_file = Path(__file__).parent / settings_path
    if not config_file.is_file():
        # No settings file – return empty mapping; caller can handle defaults
        return {}
    with config_file.open('rb') as f:
        data = tomllib.load(f)
    keys_section = data.get('keys', {})
    mapping: dict[int, int] = {}
    # left scratch (lane 0) – may be a list
    left_scratch = keys_section.get('left_scratch', [])
    for key in left_scratch:
        if isinstance(key, str) and key:
            mapping[ord(key)] = 0
    # right scratch (lane 15) – may be a list
    right_scratch = keys_section.get('right_scratch', [])
    for key in right_scratch:
        if isinstance(key, str) and key:
            mapping[ord(key)] = 15
    # normal lanes 1‑14 (or 1‑7 for 1P and 8‑14 for 2P)
    for lane in range(1, 15):
        lane_key = f"lane{lane}"
        key_val = keys_section.get(lane_key)
        if isinstance(key_val, str) and key_val:
            mapping[ord(key_val)] = lane
    return mapping
