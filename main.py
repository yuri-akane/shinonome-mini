import curses
import time
import sys
import tomllib
from pathlib import Path
from audio import AudioEngine
from player import Player
from config import load_key_to_lane as load_key_config
import random

quit_key_name = "esc"
quit_key_code = 27
scratch_side = "left"  # "left" or "right" (SP時のみ有効)

# Global mapping from key codes to lane indices

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
    global scratch_side
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

judgement_y_config = 16
judgement_offset_ms_config = 0

def load_judgement_config(settings_path: str = "settings.toml") -> tuple[int, int]:
    """settings.toml の [judgement] から judgement_y と judgement_offset_ms を読み込む。"""
    global judgement_y_config, judgement_offset_ms_config
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

auto_scratch = False

def load_auto_scratch(settings_path: str = "settings.toml") -> bool:
    """settings.toml の [play_options] auto_scratch を読み込む。"""
    global auto_scratch
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

# レーンのインデックスマッピング (左スクラッチ用: デフォルト)
CHANNEL_TO_LANE_LEFT = {
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

# レーンのインデックスマッピング (右スクラッチ用: SP時のみ)
CHANNEL_TO_LANE_RIGHT = {
    "11": 0,
    "12": 1,
    "13": 2,
    "14": 3,
    "15": 4,
    "18": 5,
    "19": 6,
    "16": 7,   # scratch (1P) → 右端
    "17": 7,   # foot pedal (1P) → 右端
    "21": 8,   # scratch (2P)
    "22": 9,
    "23": 10,
    "24": 11,
    "25": 12,
    "28": 13,
    "29": 14,
    "26": 15,
    "27": 15
}

# 実行時に決定されるマッピング
CHANNEL_TO_LANE = CHANNEL_TO_LANE_LEFT.copy()

# プレイ用のキーボード配置 (デフォルト設定: 左スクラッチ)
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

# プレイ用のキーボード配置 (デフォルト設定: 右スクラッチ)
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

# Removed global KEY_TO_LANE placeholder

def load_key_config(settings_path: str = "settings.toml") -> dict:
    """Load the custom key configuration from settings.toml.
    Returns a dict mapping integer key codes to lane indices.
    scratch_side に応じてスクラッチキーのレーン割り当てを変更する。
    """
    is_right = (scratch_side == "right")
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

        # 1P Scratch - side aware (scratch_1P or scratch_2P)
        ls_key = 'scratch_2P' if is_right else 'scratch_1P'
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

        # 2P Scratch (scratch_2P) - can be a single key or a list
        rs = keys_cfg.get('scratch_2P', ["", "\n"])
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

# レーンごとのノーツ表現
# 左スクラッチ時: 0=S, 1~7=鍵盤(白黒白黒...)
# 右スクラッチ時: 0~6=鍵盤(白黒白黒...), 7=S
LANE_CHARS_LEFT = {
    0: "XX", 
    1: "[]", 2: "::", 3: "[]", 4: "::", 5: "[]", 6: "::", 7: "[]",
    8: "[]", 9: "::", 10: "[]", 11: "::", 12: "[]", 13: "::", 14: "[]",
    15: "XX",
}
LANE_CHARS_RIGHT = {
    0: "[]", 1: "::", 2: "[]", 3: "::", 4: "[]", 5: "::", 6: "[]",
    7: "XX",
    8: "[]", 9: "::", 10: "[]", 11: "::", 12: "[]", 13: "::", 14: "[]",
    15: "XX",
}
LANE_CHARS = LANE_CHARS_LEFT.copy()

def make_on_update(stdscr, player, quit_key_code, key_to_lane):
    
    def on_update(current_time, events, event_index, initial_bpm, resolution, auto_play):
        try:
            stdscr.erase()
            
            # 画面サイズの確認 (DP時に統計情報を下げたため、必要なYサイズを拡張)
            max_y, max_x = stdscr.getmaxyx()
            # DP時は start_y + 15 + 10 = 29行程度必要になるため、少し余裕を持って required_y = 32 とします。
            is_dp = (player.chart.get('mode', 'SP') == 'DP')
            required_y = 32 if is_dp else 22
            required_x = 100 if is_dp else 70
            if max_y < required_y or max_x < required_x:
                stdscr.addstr(0, 2, "=== TERMINAL SIZE TOO SMALL ===", curses.A_BOLD)
                stdscr.addstr(2, 2, f"Required size: {required_x} cols x {required_y} rows")
                stdscr.addstr(3, 2, f"Current size : {max_x} cols x {max_y} rows")
                
            
            # タイトル等の表示
            stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
            title = player.chart['info'].get('title', 'Unknown')
            stdscr.addstr(1, 2, f"Song: {title} / {player.chart['info'].get('artist', 'Unknown')}")
            stdscr.addstr(2, 2, f"BPM: {initial_bpm:.1f} | Time: {current_time:.2f}s")
            
            # 判定ラインとレーンの描画設定
            judgement_y = judgement_y_config
            start_y = 4
            lane_x = 4
            speed = 22.0 # 1秒あたりに進む行数
            
            # Compute lane count based on mode
            lane_count = 16 if player.chart.get('mode', 'SP') == 'DP' else 8
            # Draw vertical lane borders (including rightmost bar)
            for y in range(start_y, judgement_y):
                if lane_count == 16:
                    stdscr.addstr(y, lane_x, "|" + "    |" * 8 + " " + "|" + "    |" * 8)
                else:
                    stdscr.addstr(y, lane_x, "|" + "    |" * lane_count)
            # Draw judgement line with matching number of segments
            if lane_count == 16:
                stdscr.addstr(judgement_y, lane_x, "+" + "----+" * 8 + " " + "+" + "----+" * 8)
            else:
                stdscr.addstr(judgement_y, lane_x, "+" + "----+" * lane_count)
            
            # Individual key rendering with highlight
            if player.chart.get('mode', 'SP') == 'DP':
                key_names = [
                    "[S1]", "[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]",
                    "[8]", "[9]", "[10]", "[11]", "[12]", "[13]", "[14]", "[S2]"
                ]
            elif scratch_side == "right":
                key_names = [
                    "[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]", "[S]"
                ]
            else:
                key_names = [
                    "[S]", "[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]"
                ]
            
            # Duplicate rendering block removed - cleaned up

            for idx, name in enumerate(key_names):
                # Determine which lane index to check for a press.
                lane_idx = idx  # Since lane_to_key_idx maps 1:1, we can use idx directly.
                is_active = (current_time - player.key_pressed_time[lane_idx] < 0.12)
                attr = curses.A_REVERSE if is_active else curses.A_NORMAL
                # DPのときは1P(0~7)と2P(8~15)の間に、境界線2文字分(空白 + 新しい縦線 '|') の余分なスペースを空ける
                if lane_count == 16 and idx >= 8:
                    x = lane_x + 1 + idx * 5 + 2
                else:
                    x = lane_x + 1 + idx * 5
                stdscr.addstr(judgement_y + 1, x, name, attr)
                
            if auto_play:
                stdscr.addstr(judgement_y + 2, lane_x, "[       AUTOPLAY MODE ACTIVE       ]", curses.A_DIM)
            else:
                stdscr.addstr(judgement_y + 2, lane_x, "[       MANUAL PLAY ACTIVE         ]")
                
            stdscr.addstr(judgement_y + 4, lane_x, f"Press {quit_key_name} to quit playing")
            
            # DP stats positioning: place closer to judgement line to reduce empty space
            if player.chart.get('mode', 'SP') == 'DP':
                # Place stats just a couple lines below the judgement line
                stats_y = judgement_y + 5
                stat_x = lane_x + (lane_count // 2) * 5 + 2
            else:
                stats_y = start_y
                stat_x = lane_x + lane_count * 5 + 2

            
            # ゲージバーの作成 (20セグメント。80%クリアライン=16セグメント目)
            filled_segments = int(player.gauge / 5.0)
            bar_list = []
            for idx in range(20):
                if idx < filled_segments:
                    bar_list.append("=")
                else:
                    bar_list.append("-")
            bar_list.insert(16, "|") # 80%位置に縦棒
            gauge_bar = "".join(bar_list)
            
            gauge_attr = curses.A_BOLD
            if player.gauge >= 80.0:
                gauge_attr |= curses.A_STANDOUT # クリア範囲は強調表示
            stdscr.addstr(stats_y, stat_x, f"GAUGE: [{gauge_bar}] {player.gauge:5.1f}%", gauge_attr)
            
            max_score = player.total_playable_notes * 2
            stdscr.addstr(stats_y + 2, stat_x, f"EX SCORE: {player.ex_score:5d} / {max_score:5d}")
            
            combo_attr = curses.A_NORMAL
            if player.combo > 0 and player.combo == player.max_combo:
                combo_attr = curses.A_BOLD # 自己ベスト更新中はボールド
            stdscr.addstr(stats_y + 3, stat_x, f"COMBO   : {player.combo:5d}  (MAX: {player.max_combo:5d})", combo_attr)
            
            # Abbreviated judgement counts
            stdscr.addstr(stats_y + 5, stat_x, f"P: {player.perfect_count:3d} G: {player.great_count:3d} g: {player.good_count:3d} B: {player.bad_count:3d} M: {player.miss_count:3d}", curses.A_UNDERLINE)
            # -----------------------------------------------------------
            
            # 判定表示 (0.5秒間表示する)
            if player.last_judgement and (current_time - player.judgement_time < 0.5):
                j_str = f"  {player.last_judgement}  "
                attr = curses.A_BOLD
                if player.last_judgement == "PERFECT":
                    attr |= curses.A_UNDERLINE | curses.A_STANDOUT
                elif player.last_judgement == "GREAT":
                    attr |= curses.A_STANDOUT
                elif player.last_judgement == "GOOD":
                    attr |= curses.A_BOLD
                elif player.last_judgement == "BAD":
                    attr = curses.A_DIM
                elif player.last_judgement == "MISS":
                    attr |= curses.A_BLINK
                    
                stdscr.addstr(judgement_y + 6, lane_x + 12, j_str, attr)
                
                # コンボ表示
                if player.combo >= 3 and player.last_judgement in ["PERFECT", "GREAT", "GOOD"]:
                    stdscr.addstr(judgement_y + 7, lane_x + 14, f"{player.combo} COMBO", curses.A_BOLD)
            
            # 描画対象のノーツを走査して描画
            for i in range(event_index, len(events)):
                event = events[i]
                
                # すでに処理済みのノーツ（叩かれた、あるいは見逃した）は描画しない
                if event.get('state', 0) != 0:
                    continue
                    
                channel = event.get('channel')
                if not channel or channel not in player.channel_to_lane:
                    continue
                lane_idx = player.channel_to_lane[channel]
                note_str = LANE_CHARS[lane_idx]
                
                # 再生時間を秒単位で計算
                target_seconds = (event['time'] / resolution) * (60 / initial_bpm)
                
                # 画面上のY座標を算出 (未来のノーツは上に配置される)
                y = judgement_y - int((target_seconds - current_time) * speed)
                
                # レーン描画範囲内にあれば描画
                if start_y <= y < judgement_y:
                    # DPのときは1P(0~7)と2P(8~15)の間に、境界線2文字分(空白 + 新しい縦線 '|') の余分なスペースを空ける
                    if lane_count == 16 and lane_idx >= 8:
                        x = lane_x + 1 + lane_idx * 5 + 2
                    else:
                        x = lane_x + 1 + lane_idx * 5
                    stdscr.addstr(y, x, note_str)
                elif y >= judgement_y:
                    # 判定ライン通過時のフラッシュ演出
                    if current_time - target_seconds < 0.08:
                        if lane_count == 16 and lane_idx >= 8:
                            x = lane_x + 1 + lane_idx * 5 + 2
                        else:
                            x = lane_x + 1 + lane_idx * 5
                        stdscr.addstr(judgement_y, x, "FL", curses.A_REVERSE)
                
                # 画面外上部にまだ出現していない遠すぎるノーツに達したらループを抜ける（最適化）
                if y < 0:
                    break

            # --- ビートインジケーター（判定ライン左欄外に表示）---
            beat_seconds = 60.0 / initial_bpm
            beat_number = int(current_time / beat_seconds)
            # * : 1拍ON → 1拍OFF の2拍ループ
            if beat_number % 2 == 0:
                stdscr.addstr(judgement_y, lane_x - 2, "*", curses.A_BOLD)
            else:
                stdscr.addstr(judgement_y, lane_x - 2, " ")
            # |/-\ : 0.5拍ごとに1ステップ進む（計2拍で1周）
            rotation_symbols = ["|", "/", "-", "\\"]
            half_beat_number = int(current_time / (beat_seconds * 0.5))
            rot_char = rotation_symbols[half_beat_number % 4]
            stdscr.addstr(judgement_y + 1, lane_x - 2, rot_char, curses.A_BOLD)

            # 中断・プレイキーの入力処理（ノンブロッキング）
            key = stdscr.getch()
            if key == quit_key_code:
                player.is_playing = False
            elif key in key_to_lane:
                if not auto_play:
                    player.press_key(key_to_lane[key])
                
            stdscr.refresh()
        except curses.error:
            pass
    return on_update
# stray triple-quote removed

def main(stdscr):
    # Some terminals may not support cursor visibility changes; ignore errors
    global scratch_side
    global LANE_CHARS

    try:
        curses.curs_set(0)
        stdscr.nodelay(True)
    except curses.error:
        pass
    
    ae = AudioEngine()
    # Initialize lane mapping (will be updated after scratch side handling)
    channel_to_lane = {}
    player = Player(ae, channel_to_lane)  # placeholder, will be set correctly later
    
    # 引数があればロード
    if len(sys.argv) > 1:
        try:
            player.load_chart(sys.argv[1])
            stdscr.addstr(4, 2, f"Loaded: {player.chart['info']['title']}")
            stdscr.addstr(6, 2, "Press 'p' to start MANUAL PLAY")
            stdscr.addstr(7, 2, "Press 'a' to start AUTOPLAY")
            stdscr.addstr(9, 2, f"Press '{quit_key_name}' to quit")
        except Exception as e:
            stdscr.addstr(4, 2, f"Error: {e}")
    else:
        stdscr.addstr(4, 2, "Please specify a BMS file as an argument.")
        stdscr.addstr(5, 2, "Example: python3 main.py path/to/song.bms")


    scratch_side = load_scratch_side()
    # SP時にスクラッチ位置に応じてマッピングを切替 (DPは常に左右固定)
    if player.chart and player.chart.get('mode', 'SP') == 'SP' and scratch_side == "right":
        channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
        LANE_CHARS = LANE_CHARS_RIGHT.copy()
    else:
        channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        LANE_CHARS = LANE_CHARS_LEFT.copy()
    # Sync player mapping
    player.channel_to_lane = channel_to_lane
    KEY_TO_LANE = load_key_config()
    quit_key_code = load_quit_key()
    load_judgement_config()
    
    # プレイオプションのデフォルトロード
    load_auto_scratch()
    opt_autoplay = False
    opt_autoscratch = auto_scratch
    opt_mirror = False
    opt_random = False
    opt_easy = False
    opt_scratch_side = scratch_side  # settings.toml からロードされた初期値 ("left" または "right")
    
    try:
        config_file = Path(__file__).parent / "settings.toml"
        if config_file.is_file():
            with config_file.open('rb') as f:
                data = tomllib.load(f)
            play_opts = data.get('play_options', {})
            opt_autoplay = play_opts.get('autoplay', False)
            opt_mirror = play_opts.get('mirror', False)
            opt_random = play_opts.get('random', False)
            opt_easy = play_opts.get('easy_mode', False)
    except Exception:
        pass

    running = True
    while running:
        stdscr.erase()
        stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
        
        if player.chart:
            stdscr.addstr(2, 2, f"Loaded Song: {player.chart['info']['title']}")
            
            is_dp_mode = (player.chart.get('mode', 'SP') == 'DP')
            
            # プレイオプション設定の表示
            stdscr.addstr(4, 2, "=== PLAY OPTIONS ===")
            stdscr.addstr(5, 2, f"  [A] AUTO PLAY    : {'ON' if opt_autoplay else 'OFF'}")
            stdscr.addstr(6, 2, f"  [S] AUTO SCRATCH : {'ON' if opt_autoscratch else 'OFF'}")
            stdscr.addstr(7, 2, f"  [M] MIRROR       : {'ON' if opt_mirror else 'OFF'}")
            stdscr.addstr(8, 2, f"  [R] RANDOM       : {'ON' if opt_random else 'OFF'}")
            stdscr.addstr(9, 2, f"  [E] EASY         : {'ON' if opt_easy else 'OFF'}")
            if not is_dp_mode:
                stdscr.addstr(10, 2, f"  [L] SCRATCH SIDE : {opt_scratch_side.upper()}")
            
            stdscr.addstr(12, 2, "Press key [A/S/M/R/E" + ("" if is_dp_mode else "/L") + "] to toggle option.")
            stdscr.addstr(14, 2, "Press [Enter] to START PLAY")
            stdscr.addstr(15, 2, f"Press [{quit_key_name}] to Quit")
        else:
            stdscr.addstr(2, 2, "Please specify a BMS file as an argument.")
            stdscr.addstr(3, 2, "Example: python3 main.py path/to/song.bms")
            stdscr.addstr(5, 2, f"Press [{quit_key_name}] to Quit")

        stdscr.refresh()
        
        key = stdscr.getch()
        if key == quit_key_code:
            running = False
        elif player.chart:
            if key in (ord('a'), ord('A')):
                opt_autoplay = not opt_autoplay
            elif key in (ord('s'), ord('S')):
                opt_autoscratch = not opt_autoscratch
            elif key in (ord('m'), ord('M')):
                opt_mirror = not opt_mirror
            elif key in (ord('r'), ord('R')):
                opt_random = not opt_random
            elif key in (ord('e'), ord('E')):
                opt_easy = not opt_easy
            elif not is_dp_mode and key in (ord('l'), ord('L')):
                opt_scratch_side = "right" if opt_scratch_side == "left" else "left"
            elif key in (10, 13):  # Enter key to start play
                # 決定されたスクラッチサイドに合わせて、キー構成とチャンネルマッピングを再生成する
                scratch_side = opt_scratch_side
                
                # Determine initial lane mapping based on scratch side
                if not is_dp_mode and scratch_side == "right":
                    channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
                    LANE_CHARS = LANE_CHARS_RIGHT.copy()
                else:
                    channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
                    LANE_CHARS = LANE_CHARS_LEFT.copy()
                # Recompute keyboard-to-lane mapping to match the selected scratch side
                KEY_TO_LANE = load_key_config()
                # Sync player mapping
                player.channel_to_lane = channel_to_lane

                max_lane = 15 if player.chart.get('mode', 'SP') == 'DP' else 7
                # Determine scratch lanes based on mode
                if player.chart.get('mode', 'SP') == 'DP':
                    scratch_lanes = {0, max_lane}
                else:
                    scratch_lanes = {0}
                key_lanes = [i for i in range(max_lane + 1) if i not in scratch_lanes]
                lane_map = {}
                if opt_random:
                    if player.chart.get('mode', 'SP') == 'DP':
                        # DP: split randomization into left (1-7) and right (8-14) groups
                        left_keys = list(range(1, 8))
                        right_keys = list(range(8, max_lane))  # max_lane is 15, so up to 14
                        shuffled_left = left_keys[:]
                        shuffled_right = right_keys[:]
                        random.shuffle(shuffled_left)
                        random.shuffle(shuffled_right)
                        lane_map = {}
                        lane_map.update(dict(zip(left_keys, shuffled_left)))
                        lane_map.update(dict(zip(right_keys, shuffled_right)))
                    else:
                        shuffled = key_lanes[:]
                        random.shuffle(shuffled)
                        lane_map = dict(zip(key_lanes, shuffled))
                elif opt_mirror:
                    # Mirror mapping differs for SP and DP modes
                    if player.chart.get('mode', 'SP') == 'DP':
                        # DP: exclude both scratch lanes (0 and max_lane=15), map 1↔7, 2↔6, ..., 7↔1, 8↔14, 9↔13, ..., 14↔8
                        lane_map = {lane: (max_lane // 2 + 1 - lane) if lane <= (max_lane // 2) else (max_lane + max_lane // 2 - lane) for lane in key_lanes}
                    else:
                        # SP: exclude single scratch lane (0), map 1↔7, 2↔6, ..., 7↔1,
                        lane_map = {lane: (max_lane + 1 - lane) for lane in key_lanes}
                # Apply lane_map to note channel mapping and lane characters
                if lane_map:
                    # Remap note channels to new lanes for mirrored/random behavior.
                    channel_to_lane = {ch: lane_map.get(lane, lane) for ch, lane in channel_to_lane.items()}
                # Synchronize Player mapping after lane remap
                player.channel_to_lane = channel_to_lane
                # KEY_TO_LANE (keyboard input) remains unchanged to preserve key positions and highlights


                
                player.auto_scratch = opt_autoscratch
                player.easy_mode = opt_easy
                player.judgement_offset_ms = judgement_offset_ms_config
                
                on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE)
                player.play(on_update=on_update, auto_play=opt_autoplay)
                running = False
        
        time.sleep(0.05)        
    ae.close()

if __name__ == "__main__":
    curses.wrapper(main)
