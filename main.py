import curses
import time
import sys
import os
import tomllib
from pathlib import Path
from audio import AudioEngine
from player import Player
from config import load_key_config, load_quit_key, load_scratch_side, load_judgement_config, load_auto_scratch, load_show_measure_lines
import config
import random
from constants import (
    CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT,
    LANE_CHARS_LEFT, LANE_CHARS_RIGHT,
    KEY_NAMES_DP, KEY_NAMES_RIGHT, KEY_NAMES_LEFT
)

# レーンごとのノーツ表現
# 左スクラッチ時: 0=S, 1~7=鍵盤(白黒白黒...)
# 右スクラッチ時: 0~6=鍵盤(白黒白黒...), 7=S
LANE_CHARS = LANE_CHARS_LEFT.copy()


def make_on_update(stdscr, player, quit_key_code, key_to_lane, judgement_y_config):

    def on_update(current_time, events, event_index, initial_bpm, resolution, auto_play):
        try:
            stdscr.erase()

            # 画面サイズの確認 (DP時に統計情報を下げたため、必要なYサイズを拡張)
            max_y, max_x = stdscr.getmaxyx()
            # DP時は start_y + 15 + 10 = 29行程度必要、少し余裕を持って required_y = 32 とします。
            is_dp = (player.chart.get('mode', 'SP') == 'DP')
            required_y = 32 if is_dp else 22
            required_x = 100 if is_dp else 70
            if max_y < required_y or max_x < required_x:
                stdscr.addstr(0, 2, "=== TERMINAL SIZE TOO SMALL ===", curses.A_BOLD)
                stdscr.addstr(2, 2, f"Required size: {required_x} cols x {required_y} rows")
                stdscr.addstr(3, 2, f"Current size : {max_x} cols x {max_y} rows")

            # 判定ラインとレーンの描画設定
            judgement_y = judgement_y_config
            start_y = 4
            lane_x = 4
            speed = 22.0 # 1秒あたりに進む行数

            if getattr(player, 'timeline', None):
                beat_duration = 60.0 / player.initial_bpm
                scale = speed * beat_duration
                _, player_height, current_bpm, _ = player.timeline.get_state(current_time)
            else:
                scale = speed
                player_height = current_time
                current_bpm = getattr(player, 'current_bpm', initial_bpm)

            # タイトル等の表示
            stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
            title = player.chart['info'].get('title', 'Unknown')
            stdscr.addstr(1, 2, f"Song: {title} / {player.chart['info'].get('artist', 'Unknown')}")
            stdscr.addstr(2, 2, f"BPM: {current_bpm:.1f} | Time: {current_time:.2f}s")

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
                key_names = KEY_NAMES_DP
            elif config.scratch_side == "right":
                key_names = KEY_NAMES_RIGHT
            else:
                key_names = KEY_NAMES_LEFT
            
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
                
            stdscr.addstr(judgement_y + 4, lane_x, f"Press {config.quit_key_name} to quit playing")
            
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
                is_measure_line = (channel == 'measure_line')
                if is_measure_line and not getattr(player, 'show_measure_lines', True):
                    continue
                if not is_measure_line:
                    if not channel or channel not in player.channel_to_lane:
                        continue
                    lane_idx = player.channel_to_lane[channel]
                    note_str = LANE_CHARS[lane_idx]
                
                # 再生時間と座標計算
                target_seconds = event['time']
                if getattr(player, 'timeline', None):
                    note_height = player.timeline.get_height_at_beat(event['beat'])
                else:
                    note_height = target_seconds
                
                # 画面上のY座標を算出 (未来 of notes will be placed higher)
                y = judgement_y - int((note_height - player_height) * scale)
                
                # レーン描画範囲内にあれば描画
                if start_y <= y < judgement_y:
                    if is_measure_line:
                        if lane_count == 16:
                            line_str = "+" + "----+" * 8 + " " + "+" + "----+" * 8
                        else:
                            line_str = "+" + "----+" * lane_count
                        stdscr.addstr(y, lane_x, line_str, curses.A_DIM)
                    else:
                        # DPのときは1P(0~7)と2P(8~15)の間に、境界線2文字分(空白 + 新しい縦線 '|') の余分なスペースを空ける
                        if lane_count == 16 and lane_idx >= 8:
                            x = lane_x + 1 + lane_idx * 5 + 2
                        else:
                            x = lane_x + 1 + lane_idx * 5
                        stdscr.addstr(y, x, note_str)
                elif y >= judgement_y and not is_measure_line:
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

def main(stdscr):
    # Some terminals may not support cursor visibility changes; ignore errors
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
            stdscr.addstr(9, 2, f"Press '{config.quit_key_name}' to quit")
        except Exception as e:
            stdscr.addstr(4, 2, f"Error: {e}")
    else:
        stdscr.addstr(4, 2, "Please specify a BMS file as an argument.")
        stdscr.addstr(5, 2, "Example: python3 main.py path/to/song.bms")


    config.scratch_side = load_scratch_side()
    # SP時にスクラッチ位置に応じてマッピングを切替 (DPは常に左右固定)
    if player.chart and player.chart.get('mode', 'SP') == 'SP' and config.scratch_side == "right":
        channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
        LANE_CHARS = LANE_CHARS_RIGHT.copy()
    else:
        channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        LANE_CHARS = LANE_CHARS_LEFT.copy()
    # Sync player mapping
    is_dp = (player.chart.get('mode', 'SP') == 'DP') if player.chart else False
    KEY_TO_LANE = load_key_config(is_dp=is_dp)
    quit_key_code = load_quit_key()
    judgement_y_config, judgement_offset_ms_config = load_judgement_config()
    
    # プレイオプションのデフォルトロード
    opt_autoplay = False
    opt_autoscratch = load_auto_scratch()
    opt_mirror = False
    opt_random = False
    opt_easy = False
    opt_show_measure_lines = True
    opt_scratch_side = config.scratch_side  # settings.toml からロードされた初期値 ("left" または "right")
    
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
            opt_show_measure_lines = play_opts.get('show_measure_lines', True)
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
            stdscr.addstr(10, 2, f"  [O] SHOW MEASURES: {'ON' if opt_show_measure_lines else 'OFF'}")
            if not is_dp_mode:
                stdscr.addstr(11, 2, f"  [L] SCRATCH SIDE : {opt_scratch_side.upper()}")
            
            stdscr.addstr(13, 2, "Press key [A/S/M/R/E/O" + ("" if is_dp_mode else "/L") + "] to toggle option.")
            stdscr.addstr(15, 2, "Press [Enter] to START PLAY")
            stdscr.addstr(16, 2, f"Press [{config.quit_key_name}] to Quit")
        else:
            stdscr.addstr(2, 2, "Please specify a BMS file as an argument.")
            stdscr.addstr(3, 2, "Example: python3 main.py path/to/song.bms")
            stdscr.addstr(5, 2, f"Press [{config.quit_key_name}] to Quit")

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
            elif key in (ord('o'), ord('O')):
                opt_show_measure_lines = not opt_show_measure_lines
            elif not is_dp_mode and key in (ord('l'), ord('L')):
                opt_scratch_side = "right" if opt_scratch_side == "left" else "left"
            elif key in (10, 13):  # Enter key to start play
                # 決定されたスクラッチサイドに合わせて、キー構成とチャンネルマッピングを再生成する
                config.scratch_side = opt_scratch_side
                
                # Determine initial lane mapping based on scratch side
                if not is_dp_mode and config.scratch_side == "right":
                    channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
                    LANE_CHARS = LANE_CHARS_RIGHT.copy()
                else:
                    channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
                    LANE_CHARS = LANE_CHARS_LEFT.copy()
                # Recompute keyboard-to-lane mapping to match the selected scratch side
                KEY_TO_LANE = load_key_config(is_dp=is_dp_mode)
                # Sync player mapping
                player.channel_to_lane = channel_to_lane

                max_lane = 15 if player.chart.get('mode', 'SP') == 'DP' else 7
                # Determine scratch lanes based on mode and side
                if player.chart.get('mode', 'SP') == 'DP':
                    scratch_lanes = {0, max_lane}
                else:
                    scratch_lanes = {7} if config.scratch_side == "right" else {0}
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
                player.show_measure_lines = opt_show_measure_lines
                player.judgement_offset_ms = judgement_offset_ms_config
                
                on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE, judgement_y_config)
                player.play(on_update=on_update, auto_play=opt_autoplay)
                running = False
        
        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
    ae.close()

if __name__ == "__main__":
    curses.wrapper(main)
