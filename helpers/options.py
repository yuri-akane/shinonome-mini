import tomllib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import argparse

# Default key map fallback constants
DEFAULT_KEY_TO_LANE_LEFT = {
    # Player 1 (左スクラッチ)
    ord(' '): 0,  # Space: Scratch (1P)
    ord('a'): 0,  # a: Scratch (1P)
    ord('z'): 1, ord('s'): 2, ord('x'): 3, ord('d'): 4, ord('c'): 5, ord('f'): 6, ord('v'): 7,
    # Player 2
    ord(','): 8, ord('l'): 9, ord('.'): 10, ord(';'): 11, ord("/"): 12, ord(':'): 13, ord('\\'): 14,
    ord(']'): 15,
}

DEFAULT_KEY_TO_LANE_RIGHT = {
    # Player 1 (右スクラッチ: 鍵盤が0~6、スクラッチが7)
    ord('z'): 0, ord('s'): 1, ord('x'): 2, ord('d'): 3, ord('c'): 4, ord('f'): 5, ord('v'): 6,
    ord(' '): 7,  # Space: Scratch (1P) → 右端
    ord('a'): 7,  # a: Scratch (1P) → 右端
    # Player 2
    ord(','): 8, ord('l'): 9, ord('.'): 10, ord(';'): 11, ord("/"): 12, ord(':'): 13, ord('\\'): 14,
    ord(']'): 15,
}

DEFAULT_4K_KEYS = ['d', 'f', 'j', 'k']
DEFAULT_6K_KEYS = ['s', 'd', 'f', 'j', 'k', 'l']
DEFAULT_9K_KEYS = ['z', 's', 'x', 'd', 'c', 'f', 'v', 'g', 'b']

DEFAULT_KEY_TO_LANE_5K_LEFT = {
    ord(' '): 0, ord('a'): 0, ord('z'): 1, ord('s'): 2, ord('x'): 3, ord('d'): 4, ord('c'): 5
}
DEFAULT_KEY_TO_LANE_5K_RIGHT = {
    ord('z'): 0, ord('s'): 1, ord('x'): 2, ord('d'): 3, ord('c'): 4, ord(' '): 5, ord('a'): 5
}
DEFAULT_KEY_TO_LANE_10K = {
    ord(' '): 0, ord('a'): 0,
    ord('z'): 1, ord('s'): 2, ord('x'): 3, ord('d'): 4, ord('c'): 5,
    ord('.'): 6, ord(';'): 7, ord('/'): 8, ord(':'): 9, ord("\\"): 10,
    10: 11, 13: 11
}

def load_toml(settings_path: str = "settings.toml") -> dict:
    """Load settings.toml and return its content as a dict.
    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    config_file = Path(settings_path)
    if not config_file.is_absolute():
        config_file = Path(__file__).parent.parent / settings_path
    if not config_file.is_file():
        return {}
    try:
        with config_file.open('rb') as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _resolve_key_code(k: Any) -> int:
    import curses
    if isinstance(k, str):
        uk = k.upper()
        if uk == 'KEY_UP':
            return curses.KEY_UP
        if uk == 'KEY_DOWN':
            return curses.KEY_DOWN
        if len(k) == 1:
            return ord(k)
    elif isinstance(k, int):
        return k
    return curses.KEY_UP  # fallback default


def _resolve_quit_key(key_val: Any) -> tuple[int, str]:
    if isinstance(key_val, str):
        key_val_lc = key_val.lower()
        if key_val_lc == 'esc':
            return 27, "esc"
        if len(key_val_lc) == 1:
            return ord(key_val_lc), key_val_lc
    return 27, "esc"


def _scratch_lanes(mode_upper: str, scratch_side: str) -> tuple[int, int]:
    if mode_upper in ("4K", "6K"):
        return 0, 0
    if mode_upper == "9K":
        return 0, 8
    if mode_upper == "5K":
        lane = 5 if scratch_side == "right" else 0
        return lane, lane
    if mode_upper == "10K":
        return 0, 11
    if mode_upper == "7K":
        lane = 7 if scratch_side == "right" else 0
        return lane, lane
    return 0, 15


@dataclass
class Options:
    # Display & Command Line
    bmsfile: str | None = None
    display_mode: str = "mini"
    nomenu: bool = False
    force_mode: str | None = None

    # Scratch
    scratch_side: str = "left"

    # Play options
    autoplay: bool = False
    mirror: bool = False
    random: bool = False
    easy: bool = False
    hard: bool = False
    solid: bool = False
    autoscratch: bool = False
    show_measure_lines: bool = True
    show_ln_end_head: bool = False
    show_result: bool = True
    stdout_result: bool = False
    hispeed: float = 1.0

    def toggle_display_mode(self) -> None:
        modes = ["mini", "tiny", "mw", "none"]
        if self.display_mode not in modes:
            self.display_mode = "mini"
        else:
            idx = modes.index(self.display_mode)
            self.display_mode = modes[(idx + 1) % len(modes)]

    # Key config
    speedup_key: str = "KEY_UP"
    speeddown_key: str = "KEY_DOWN"
    speedup_code: int = 259  # curses.KEY_UP default value
    speeddown_code: int = 258  # curses.KEY_DOWN default value
    quit_key: str = "esc"
    quit_key_code: int = 27
    quit_key_name: str = "esc"

    # Judgement
    judgement_y: int = 16
    judgement_offset_ms: int = 0
    note_display_offset_ms: int = 0

    # Audio
    sample_rate: int = 24000
    nchannels: int = 2

    # BMS
    bms_encoding: str = "cp932"

    # Modifiers
    use_pynput: bool = True

    # Raw loaded toml dict for custom key bindings & modifiers
    raw_toml: dict[str, Any] = field(default_factory=dict)

    def load_key_config(self, scratch_side: str | None = None, is_dp: bool = False, mode: str | None = None) -> dict:
        """Load key configuration mapping key codes to lane indices."""
        if scratch_side is None:
            scratch_side = self.scratch_side
        if mode is None:
            mode = "14K" if is_dp else "7K"
        mode_upper = mode.upper()
        config_data = self.raw_toml

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

        new_map: dict[int, int] = {}

        if mode_upper == "4K":
            cfg_4k = config_data.get('keys_4k', {}) if config_data else {}
            keys_cfg = config_data.get('keys', {}) if config_data else {}
            for i in range(4):
                lane_val = cfg_4k.get(f'lane{i}')
                if lane_val is None:
                    lane_val = keys_cfg.get(f'lane{i}')
                if lane_val is None:
                    lane_val = DEFAULT_4K_KEYS[i]
                add_keys(new_map, lane_val, i)
            return new_map

        elif mode_upper == "6K":
            cfg_6k = config_data.get('keys_6k', {}) if config_data else {}
            keys_cfg = config_data.get('keys', {}) if config_data else {}
            for i in range(6):
                lane_val = cfg_6k.get(f'lane{i}')
                if lane_val is None:
                    lane_val = keys_cfg.get(f'lane{i}')
                if lane_val is None:
                    lane_val = DEFAULT_6K_KEYS[i]
                add_keys(new_map, lane_val, i)
            return new_map

        elif mode_upper == "5K":
            is_right = (scratch_side == "right")
            scratch_lane = 5 if is_right else 0
            cfg_5k = config_data.get('keys_5k', {}) if config_data else {}
            keys_cfg = config_data.get('keys', {}) if config_data else {}

            ls_key = 'scratch_SP_right' if is_right else 'scratch_SP_left'
            ls = cfg_5k.get('scratch', keys_cfg.get(ls_key, ["a", " ", "\t"]))
            add_keys(new_map, ls, scratch_lane)

            offset = 0 if is_right else 1
            for i in range(5):
                lane_val = cfg_5k.get(f'lane{i}', keys_cfg.get(f'lane{i}'))
                if lane_val is not None:
                    add_keys(new_map, lane_val, i + offset)

            if not new_map:
                return DEFAULT_KEY_TO_LANE_5K_RIGHT if is_right else DEFAULT_KEY_TO_LANE_5K_LEFT
            return new_map

        elif mode_upper == "9K":
            cfg_9k = config_data.get('keys_9k', {}) if config_data else {}
            keys_cfg = config_data.get('keys', {}) if config_data else {}
            fallback_lanes = [0, 1, 2, 3, 4, 8, 9, 10, 11]

            for i in range(9):
                lane_val = cfg_9k.get(f'lane{i}')
                if lane_val is None:
                    fb_i = fallback_lanes[i]
                    lane_val = keys_cfg.get(f'lane{fb_i}')
                if lane_val is None:
                    lane_val = DEFAULT_9K_KEYS[i]
                add_keys(new_map, lane_val, i)

            return new_map

        elif mode_upper == "10K":
            cfg_10k = config_data.get('keys_10k', {}) if config_data else {}
            keys_cfg = config_data.get('keys', {}) if config_data else {}

            ls = cfg_10k.get('scratch_1p', keys_cfg.get('scratch_DP_left', ["a", " ", "\t"]))
            add_keys(new_map, ls, 0)

            for i in range(5):
                lane_val = cfg_10k.get(f'lane{i}', keys_cfg.get(f'lane{i}'))
                if lane_val is not None:
                    add_keys(new_map, lane_val, i + 1)

            for i in range(5):
                lane_val = cfg_10k.get(f'lane{i+5}', keys_cfg.get(f'lane{i+7}'))
                if lane_val is not None:
                    add_keys(new_map, lane_val, i + 6)

            rs = cfg_10k.get('scratch_2p', keys_cfg.get('scratch_DP_right', ["", "\n"]))
            add_keys(new_map, rs, 11)

            if not new_map:
                return DEFAULT_KEY_TO_LANE_10K
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

        if mode_upper == "14K":
            ls_key = 'scratch_DP_left'
        else:
            ls_key = 'scratch_SP_right' if is_right else 'scratch_SP_left'
        ls = keys_cfg.get(ls_key, ["a", " ", "\t"])
        add_keys(new_map, ls, scratch_lane)

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

        if mode_upper == "14K":
            for i in range(7, 14):
                lane_val = keys_cfg.get(f'lane{i}')
                if lane_val is not None:
                    add_keys(new_map, lane_val, i + 1)
            rs = keys_cfg.get('scratch_DP_right', ["", "\n"])
            add_keys(new_map, rs, 15)

        res_map = new_map if new_map else default_map.copy()
        if mode_upper == "7K":
            res_map = {k: v for k, v in res_map.items() if 0 <= v <= 7}
        return res_map

    def load_modifier_keys(self, mode: str = "7K", scratch_side: str | None = None) -> dict:
        """Load modifier key mappings from TOML."""
        if scratch_side is None:
            scratch_side = self.scratch_side
        mode_upper = mode.upper() if mode else "7K"
        scratch_1p_lane, scratch_2p_lane = _scratch_lanes(mode_upper, scratch_side)

        data = self.raw_toml
        mod_cfg = data.get('modifiers', {}) if data else {}
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
                    result[base] = lane
                elif name_lc.endswith('_r'):
                    base = name_lc[:-2]
                    result[f"{base}_r"] = lane
                else:
                    result[name_lc] = lane

        if not result and data:
            key_cfg = data.get('keys', {})
            left_scratch = key_cfg.get('scratch_SP_left', [])
            if isinstance(left_scratch, str):
                left_scratch = [left_scratch]
            for k in left_scratch:
                if isinstance(k, str) and k.lower() == 'shift':
                    result['shift'] = scratch_1p_lane
                    break

        return result


def load_options(args: argparse.Namespace | None = None, settings_path: str = "settings.toml") -> Options:
    """Load unified configuration options following priority rule:
    CLI parameters > settings.toml > Default values.
    """
    opts = Options()

    # 1. Load settings.toml
    toml_data = load_toml(settings_path)
    opts.raw_toml = toml_data

    # Display section
    disp_cfg = toml_data.get('display', {})
    if 'mode' in disp_cfg:
        raw_mode = str(disp_cfg['mode']).lower().strip()
        if raw_mode in ('none', 'soundonly'):
            opts.display_mode = 'soundonly'
        elif raw_mode == 'tiny':
            opts.display_mode = 'tiny'
        elif raw_mode in ('mw', 'scan'):
            opts.display_mode = 'mw'
        elif raw_mode == 'mini':
            opts.display_mode = 'mini'

    # Scratch section
    scratch_cfg = toml_data.get('scratch', {})
    if 'side' in scratch_cfg:
        side = str(scratch_cfg['side']).lower().strip()
        if side in ('left', 'right'):
            opts.scratch_side = side

    # Play options section
    play_opts = toml_data.get('play_options', {})
    opts.autoplay = play_opts.get('autoplay', opts.autoplay)
    opts.mirror = play_opts.get('mirror', opts.mirror)
    opts.random = play_opts.get('random', opts.random)
    opts.easy = play_opts.get('easy_mode', opts.easy)
    opts.hard = play_opts.get('hard_gauge', opts.hard)
    opts.solid = play_opts.get('solid_gauge', opts.solid)
    opts.autoscratch = play_opts.get('auto_scratch', opts.autoscratch)
    opts.show_measure_lines = play_opts.get('show_measure_lines', opts.show_measure_lines)
    opts.show_ln_end_head = play_opts.get('show_ln_end_head', opts.show_ln_end_head)
    opts.show_result = play_opts.get('show_result', opts.show_result)
    opts.stdout_result = play_opts.get('stdout_result', opts.stdout_result)
    opts.hispeed = float(play_opts.get('hispeed', opts.hispeed))
    opts.speedup_key = play_opts.get('speedup_key', opts.speedup_key)
    opts.speeddown_key = play_opts.get('speeddown_key', opts.speeddown_key)

    opts.speedup_code = _resolve_key_code(opts.speedup_key)
    opts.speeddown_code = _resolve_key_code(opts.speeddown_key)

    # Quit section
    quit_cfg = toml_data.get('quit', {})
    if 'key' in quit_cfg:
        opts.quit_key = str(quit_cfg['key'])
    opts.quit_key_code, opts.quit_key_name = _resolve_quit_key(opts.quit_key)

    # Judgement section
    judg_cfg = toml_data.get('judgement', {})
    opts.judgement_y = int(judg_cfg.get('judgement_y', opts.judgement_y))
    opts.judgement_offset_ms = int(judg_cfg.get('judgement_offset_ms', opts.judgement_offset_ms))
    opts.note_display_offset_ms = int(judg_cfg.get('note_display_offset_ms', opts.note_display_offset_ms))

    # Audio section
    audio_cfg = toml_data.get('audio', {})
    sample_rate = audio_cfg.get('sample_rate', opts.sample_rate)
    nchannels = audio_cfg.get('nchannels', opts.nchannels)
    if isinstance(sample_rate, int) and sample_rate > 0:
        opts.sample_rate = sample_rate
    if nchannels in (1, 2):
        opts.nchannels = nchannels

    # BMS section
    bms_cfg = toml_data.get('bms', {})
    raw_enc = str(bms_cfg.get('encoding', opts.bms_encoding)).lower().strip().replace('-', '_')
    if raw_enc in ('cp932', 'shift_jis', 'sjis', 'shiftjis'):
        opts.bms_encoding = 'cp932'
    elif raw_enc in ('cp949', 'euc_kr', 'euckr'):
        opts.bms_encoding = 'cp949'
    elif raw_enc in ('utf_8', 'utf8'):
        opts.bms_encoding = 'utf-8'

    # Modifiers section
    mod_cfg = toml_data.get('modifiers', {})
    opts.use_pynput = bool(mod_cfg.get('use_pynput', opts.use_pynput))

    # 2. Override with CLI args (if provided)
    if args is not None:
        if getattr(args, 'bmsfile', None) is not None:
            opts.bmsfile = args.bmsfile

        if getattr(args, 'cli_display_mode_set', False) and getattr(args, 'display_mode', None) is not None:
            opts.display_mode = args.display_mode

        if hasattr(args, 'autoplay'):
            opts.autoplay = bool(args.autoplay)
        if hasattr(args, 'mirror'):
            opts.mirror = bool(args.mirror)
        if hasattr(args, 'random'):
            opts.random = bool(args.random)
        if hasattr(args, 'easy'):
            opts.easy = bool(args.easy)
        if hasattr(args, 'hard'):
            opts.hard = bool(args.hard)
        if hasattr(args, 'solid'):
            opts.solid = bool(args.solid)
        if hasattr(args, 'autoscratch'):
            opts.autoscratch = bool(args.autoscratch)
        if hasattr(args, 'show_result'):
            opts.show_result = bool(args.show_result)
        if hasattr(args, 'stats'):
            opts.stdout_result = bool(args.stats)

        if getattr(args, 'easy', False) and getattr(args, 'hard', False):
            opts.easy = False

        if getattr(args, 'nomenu', False):
            opts.nomenu = True
        if getattr(args, 'force_mode', None) is not None:
            opts.force_mode = args.force_mode

    # Forced autoplay if soundonly/none
    if opts.display_mode in ('soundonly', 'none'):
        opts.autoplay = True

    return opts
