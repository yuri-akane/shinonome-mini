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

def load_key_config(scratch_side, is_dp: bool = False, mode: str = None) -> dict:
    """Load the custom key configuration from settings.toml.
    Returns a dict mapping integer key codes to lane indices.
    """
    if mode is None:
        mode = "14K" if is_dp else "7K"
    mode_upper = mode.upper()

    config_data = _load_toml()

    def add_keys(target_dict, keys_val, lane_idx):
        if isinstance(keys_val, str):
            keys_val = [keys_val]
        elif not isinstance(keys_val, list):
            return
        for key_str in keys_val:
            if not isinstance(key_str, str):
                continue
            if len(key_str) == 1:
                target_dict[ord(key_str)] = lane_idx
            elif key_str == "\t":
                target_dict[9] = lane_idx
            elif key_str == "\n":
                target_dict[10] = lane_idx
                target_dict[13] = lane_idx

    new_map = {}

    if mode_upper == "5K":
        is_right = (scratch_side == "right")
        scratch_lane = 5 if is_right else 0
        cfg_5k = config_data.get('keys_5k', {}) if config_data else {}
        keys_cfg = config_data.get('keys', {}) if config_data else {}

        # 1P Scratch
        ls_key = 'scratch_SP_right' if is_right else 'scratch_SP_left'
        ls = cfg_5k.get('scratch', keys_cfg.get(ls_key, ["a", " ", "\t"]))
        add_keys(new_map, ls, scratch_lane)

        # 1P Keys (lane0..lane4)
        offset = 0 if is_right else 1
        for i in range(5):
            lane_val = cfg_5k.get(f'lane{i}', keys_cfg.get(f'lane{i}'))
            if lane_val is not None:
                add_keys(new_map, lane_val, i + offset)

        if not new_map:
            if is_right:
                return {ord('z'): 0, ord('s'): 1, ord('x'): 2, ord('d'): 3, ord('c'): 4, ord(' '): 5, ord('a'): 5}
            else:
                return {ord(' '): 0, ord('a'): 0, ord('z'): 1, ord('s'): 2, ord('x'): 3, ord('d'): 4, ord('c'): 5}
        return new_map

    elif mode_upper == "10K":
        cfg_10k = config_data.get('keys_10k', {}) if config_data else {}
        keys_cfg = config_data.get('keys', {}) if config_data else {}

        # 1P Scratch -> lane 0
        ls = cfg_10k.get('scratch_1p', keys_cfg.get('scratch_DP_left', ["a", " ", "\t"]))
        add_keys(new_map, ls, 0)

        # 1P Keys (lane0..lane4 -> 1..5)
        for i in range(5):
            lane_val = cfg_10k.get(f'lane{i}', keys_cfg.get(f'lane{i}'))
            if lane_val is not None:
                add_keys(new_map, lane_val, i + 1)

        # 2P Keys (lane5..lane9 in 10k config or lane7..lane11 in 7k config -> 6..10)
        for i in range(5):
            lane_val = cfg_10k.get(f'lane{i+5}', keys_cfg.get(f'lane{i+7}'))
            if lane_val is not None:
                add_keys(new_map, lane_val, i + 6)

        # 2P Scratch -> lane 11
        rs = cfg_10k.get('scratch_2p', keys_cfg.get('scratch_DP_right', ["", "\n"]))
        add_keys(new_map, rs, 11)

        if not new_map:
            return {
                ord(' '): 0, ord('a'): 0,
                ord('z'): 1, ord('s'): 2, ord('x'): 3, ord('d'): 4, ord('c'): 5,
                ord('j'): 6, ord('k'): 7, ord('l'): 8, ord(';'): 9, ord("'"): 10,
                10: 11, 13: 11
            }
        return new_map

    # 7K and 14K modes
    is_right = (scratch_side == "right") and (mode_upper == "7K")
    default_map = DEFAULT_KEY_TO_LANE_RIGHT if is_right else DEFAULT_KEY_TO_LANE_LEFT
    scratch_lane = 7 if is_right else 0

    if not config_data:
        return default_map.copy()
    keys_cfg = config_data.get('keys', {})
    if not keys_cfg:
        return default_map.copy()

    # 1P Scratch - side aware (scratch_SP_left / scratch_SP_right / scratch_DP_left)
    if mode_upper == "14K":
        ls_key = 'scratch_DP_left'
    else:
        ls_key = 'scratch_SP_right' if is_right else 'scratch_SP_left'
    ls = keys_cfg.get(ls_key, ["a", " ", "\t"])
    add_keys(new_map, ls, scratch_lane)

    # 1P Keys
    if is_right:
        for i in range(7):
            lane_val = keys_cfg.get(f'lane{i}')
            if lane_val is not None:
                add_keys(new_map, lane_val, i)
    else:
        for i in range(7):
            lane_val = keys_cfg.get(f'lane{i}')
            if lane_val is not None:
                add_keys(new_map, lane_val, i + 1)

    # 2P Keys (lane7 ~ lane13 mapped to index 8 ~ 14)
    for i in range(7, 14):
        lane_val = keys_cfg.get(f'lane{i}')
        if lane_val is not None:
            add_keys(new_map, lane_val, i + 1)

    # 2P Scratch (scratch_DP_right)
    rs = keys_cfg.get('scratch_DP_right', ["", "\n"])
    add_keys(new_map, rs, 15)

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

def load_modifier_keys(mode: str = "7K", scratch_side: str = "left") -> dict:
    """Load modifier key mappings from settings.toml.

    The [modifiers] section can define left/right modifiers using integer lane indices
    or symbolic target names (e.g. "scratch_1p", "scratch_2p", "scratch_l", "scratch_r").
    For backwards compatibility, numeric 15 (2P scratch in 14K) automatically remaps to
    10K's 2P scratch (lane 11) when playing 10K charts.
    """
    mode_upper = mode.upper() if mode else "7K"

    if mode_upper == "5K":
        scratch_1p_lane = 5 if scratch_side == "right" else 0
        scratch_2p_lane = 5 if scratch_side == "right" else 0
    elif mode_upper == "10K":
        scratch_1p_lane = 0
        scratch_2p_lane = 11
    elif mode_upper == "7K":
        scratch_1p_lane = 7 if scratch_side == "right" else 0
        scratch_2p_lane = 7 if scratch_side == "right" else 0
    else:  # 14K
        scratch_1p_lane = 0
        scratch_2p_lane = 15

    data = _load_toml()
    mod_cfg = data.get('modifiers', {})
    result: dict[str, int] = {}

    for name, target in mod_cfg.items():
        if name == 'use_pynput':
            continue

        lane = None
        if isinstance(target, int):
            if target == 15 and mode_upper == "10K":
                lane = 11
            else:
                lane = target
        elif isinstance(target, str):
            target_lc = target.lower().strip()
            if target_lc in ("scratch_1p", "scratch_l", "scratch_left", "scratch"):
                lane = scratch_1p_lane
            elif target_lc in ("scratch_2p", "scratch_r", "scratch_right"):
                lane = scratch_2p_lane
            elif target_lc.startswith("lane") and target_lc[4:].isdigit():
                lane = int(target_lc[4:])

        if lane is not None:
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
                result['shift'] = scratch_1p_lane
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

def load_audio_config() -> dict:
    """Load [audio] section from settings.toml.

    Returns a dict with the following keys:
        sample_rate (int): sampling rate in Hz (default: 24000)
        nchannels   (int): number of channels; 1=mono, 2=stereo (default: 2)
    """
    data = _load_toml()
    audio_cfg = data.get('audio', {}) if data else {}
    sample_rate = audio_cfg.get('sample_rate', 24000)
    nchannels   = audio_cfg.get('nchannels', 2)
    # 値の妥当性チェック
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        sample_rate = 24000
    if nchannels not in (1, 2):
        nchannels = 2
    return {
        'sample_rate': sample_rate,
        'nchannels':   nchannels,
    }

def load_bms_encoding() -> str:
    """Load BMS text encoding setting from settings.toml's [bms] section.
    Supports cp932 (shift-jis), cp949 (euc-kr), and utf-8.
    Defaults to 'cp932'.
    """
    data = _load_toml()
    bms_cfg = data.get('bms', {}) if data else {}
    raw_enc = str(bms_cfg.get('encoding', 'cp932')).lower().strip().replace('-', '_')

    if raw_enc in ('cp932', 'shift_jis', 'sjis', 'shiftjis'):
        return 'cp932'
    elif raw_enc in ('cp949', 'euc_kr', 'euckr', 'euc_kr'):
        return 'cp949'
    elif raw_enc in ('utf_8', 'utf8'):
        return 'utf-8'
    return 'cp932'

# -------------------------------------------------
# ファイル名・表記揺れ吸収用 Unicode 互換文字グループの定義
# -------------------------------------------------
CHAR_EQUIVALENCE_GROUPS = [
    {'\u301c', '\uff5e'},  # Wave dash (〜) vs Fullwidth tilde (～)
    {'\u2014', '\u2015'},  # Em dash (—) vs Horizontal bar (―)
    {'\u2212', '\uff0d'},  # Minus sign (−) vs Fullwidth hyphen-minus (－)
]

# 各グループ内の先頭要素（Unicode順ソート時の先頭）を代表文字に採用する
_NORMALIZE_MAP = {
    c: sorted(list(group))[0]
    for group in CHAR_EQUIVALENCE_GROUPS
    for c in group
}

def normalize_filename_chars(text: str) -> str:
    """互換文字グループに含まれる文字を統一された代表文字に正規化する。"""
    return "".join(_NORMALIZE_MAP.get(ch, ch) for ch in text)

def get_filename_variants(text: str) -> list[str]:
    """
    文字列中の互換文字（波ダッシュ、ダッシュ記号、マイナス記号等）について、
    考えられるすべての表記バリエーションのリストを返す。
    重複を除外した順序保存リスト。
    """
    variants = [text]
    for group in CHAR_EQUIVALENCE_GROUPS:
        new_variants = []
        for v in variants:
            found_chars = [ch for ch in group if ch in v]
            if not found_chars:
                if v not in new_variants:
                    new_variants.append(v)
                continue

            for src_char in found_chars:
                for target_char in group:
                    if src_char == target_char:
                        if v not in new_variants:
                            new_variants.append(v)
                    else:
                        replaced = v.replace(src_char, target_char)
                        if replaced not in new_variants:
                            new_variants.append(replaced)
        variants = new_variants
    return variants



