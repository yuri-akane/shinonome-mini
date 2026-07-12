import curses
import time
import sys
import os
import tomllib
from pathlib import Path
from audio import AudioEngine
from player import Player
#from config import load_key_config, load_quit_key, load_scratch_side, load_judgement_config, load_auto_scratch, load_modifier_keys, _load_toml
from config import load_key_config, load_quit_key, load_scratch_side, load_judgement_config, load_modifier_keys, _load_toml
import config
from on_update import make_on_update
import random
from constants import (
    CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT,
    LANE_CHARS_LEFT, LANE_CHARS_RIGHT,
    KEY_NAMES_DP, KEY_NAMES_RIGHT, KEY_NAMES_LEFT
)

def _show_game_over(stdscr, player, quit_key_code):
    """HARDゲージが0%に達したときのGAME OVER画面を表示する。
    任意キーを受け取るまでブロックする。その後呼び出し元がプログラムを終了させる。
    """
    try:
        curses.curs_set(0)
        stdscr.nodelay(False)
    except curses.error:
        pass
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()

    box_w = 50
    box_h = 18
    bx = max(0, (max_x - box_w) // 2)
    by = max(0, (max_y - box_h) // 2)

    def pr(row, col, text, attr=curses.A_NORMAL):
        try:
            stdscr.addstr(by + row, bx + col, text, attr)
        except curses.error:
            pass

    border = "+" + "-" * (box_w - 2) + "+"
    blank  = "|" + " " * (box_w - 2) + "|"
    for r in range(box_h):
        pr(r, 0, border if r in (0, box_h - 1) else blank)

    title = "G A M E   O V E R"
    pr(2, (box_w - len(title)) // 2, title, curses.A_BOLD | curses.A_STANDOUT)

    sub = "~  Hard Gauge reached 0%  ~"
    pr(4, (box_w - len(sub)) // 2, sub)

    pr(6, 4, "---  Results  ---")
    stats = [
        ("PERFECT", player.perfect_count),
        ("GREAT  ", player.great_count),
        ("GOOD   ", player.good_count),
        ("BAD    ", player.bad_count),
        ("MISS   ", player.miss_count),
    ]
    for i, (label, val) in enumerate(stats):
        pr(7 + i, 5, f"{label} : {val:5d}")

    max_score = player.total_playable_notes * 2
    pr(13, 5, f"EX SCORE : {player.ex_score:5d} / {max_score:5d}")
    pr(14, 5, f"MAX COMBO: {player.max_combo:5d}")

    #footer = "Press any key to exit"
    footer = f"Press [{config.quit_key_name}] to Quit"
    pr(16, (box_w - len(footer)) // 2, footer, curses.A_DIM)

    stdscr.refresh()
    while True:
        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
        key = stdscr.getch()
        if key == quit_key_code:
            break
        else:
            continue
    try:
        stdscr.nodelay(True)
    except curses.error:
        pass


def main(stdscr):
    # Some terminals may not support cursor visibility changes; ignore errors
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
            player.load_audio_async()  # 音声リソースをバックグラウンドでロード開始
        except Exception as e:
            stdscr.addstr(4, 2, f"Error: {e}")
    else:
        stdscr.addstr(4, 2, "Please specify a BMS file as an argument.")
        stdscr.addstr(5, 2, "Example: python3 main.py path/to/song.bms")


    opt_scratch_side = load_scratch_side()
    # SP時にスクラッチ位置に応じてマッピングを切替 (DPは常に左右固定)
    if player.chart and player.chart.get('mode', 'SP') == 'SP' and opt_scratch_side == "right":
        channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
        lane_chars = LANE_CHARS_RIGHT.copy()
    else:
        channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        lane_chars = LANE_CHARS_LEFT.copy()
    # Sync player mapping
    is_dp = (player.chart.get('mode', 'SP') == 'DP') if player.chart else False
    KEY_TO_LANE = load_key_config(opt_scratch_side, is_dp=is_dp)
    quit_key_code = load_quit_key()
    judgement_y_config, judgement_offset_ms_config = load_judgement_config()

    try:
        data = _load_toml()
        play_opts = data.get('play_options', {})
        opt_autoplay = play_opts.get('autoplay', False)
        opt_mirror = play_opts.get('mirror', False)
        opt_random = play_opts.get('random', False)
        opt_easy = play_opts.get('easy_mode', False)
        opt_hard = play_opts.get('hard_gauge', False)
        opt_show_measure_lines = play_opts.get('show_measure_lines', True)
        opt_hispeed = play_opts.get('hispeed', 1.0)  # Read hispeed from settings
        opt_autoscratch = play_opts.get('auto_scratch', False)
        # Configurable hispeed key bindings
        speedup_key = data.get('speedup_key', 'KEY_UP')
        speeddown_key = data.get('speeddown_key', 'KEY_DOWN')
        def _key_code(k):
            if isinstance(k, str):
                uk = k.upper()
                if uk == 'KEY_UP':
                    return curses.KEY_UP
                if uk == 'KEY_DOWN':
                    return curses.KEY_DOWN
                return ord(k)
            return k
        speedup_code = _key_code(speedup_key)
        speeddown_code = _key_code(speeddown_key)
    except Exception: #何かひどいことが起きたときのfallback
        opt_autoplay = True
        opt_mirror = False
        opt_random = False
        opt_easy = False
        opt_hard = False
        opt_show_measure_lines = True
        opt_hispeed = 1.0
        opt_scratch_side = "left"
        opt_autoscratch = False

    running = True
    while running:
        stdscr.erase()
        stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)

        if player.chart:
            #stdscr.addstr(2, 2, f"Song: {player.chart['info']['title']}")
            stdscr.addstr(1, 2, f"Song: {player.chart['info'].get('title', 'Unknown')} / Artist: {player.chart['info'].get('artist', 'Unknown')}")

            is_dp_mode = (player.chart.get('mode', 'SP') == 'DP')

            # ロード状態の表示
            if player.audio.is_loading:
                loaded, total = player.audio.loading_progress
                stdscr.addstr(2, 2, f"Loading audio... ({loaded}/{total})")
            else:
                stdscr.addstr(2, 2, "Audio ready.                          ")

            # プレイオプション設定の表示
            stdscr.addstr(4, 2, "=== PLAY OPTIONS ===")
            stdscr.addstr(5, 2, f"  [A] AUTO PLAY    : {'ON' if opt_autoplay else 'OFF'}")
            stdscr.addstr(6, 2, f"  [S] AUTO SCRATCH : {'ON' if opt_autoscratch else 'OFF'}")
            stdscr.addstr(7, 2, f"  [M] MIRROR       : {'ON' if opt_mirror else 'OFF'}")
            stdscr.addstr(8, 2, f"  [R] RANDOM       : {'ON' if opt_random else 'OFF'}")
            stdscr.addstr(9, 2, f"  [E] EASY         : {'ON' if opt_easy else 'OFF'}")
            stdscr.addstr(10, 2, f"  [H] HARD GAUGE   : {'ON' if opt_hard else 'OFF'}")
            stdscr.addstr(11, 2, f"  [O] SHOW MEASURES: {'ON' if opt_show_measure_lines else 'OFF'}")
            stdscr.addstr(12, 2, f"  [keyup/down] HS (Hispeed) : {opt_hispeed:.1f}")
            if not is_dp_mode:
                stdscr.addstr(13, 2, f"  [L] SCRATCH SIDE : {opt_scratch_side.upper()}")

            stdscr.addstr(14, 2, "Press key [A/S/M/R/E/H/O" + ("" if is_dp_mode else "/L") + "] to toggle option.")
            if player.is_audio_ready:
                stdscr.addstr(16, 2, "Press [Enter] to START PLAY")
            else:
                stdscr.addstr(16, 2, "[Enter] will be available after audio loads")
            stdscr.addstr(17, 2, f"Press [{config.quit_key_name}] to Quit")
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
                if opt_easy:
                    opt_hard = False  # EASYとHARDは排他
            elif key in (ord('h'), ord('H')):
                opt_hard = not opt_hard
                if opt_hard:
                    opt_easy = False  # EASYとHARDは排他
            elif key in (ord('o'), ord('O')):
                opt_show_measure_lines = not opt_show_measure_lines
            elif key == speedup_code:
                opt_hispeed = min(opt_hispeed + 0.2, 100.0)
            elif key == speeddown_code:
                opt_hispeed = max(opt_hispeed - 0.2, 0.2)
            elif not is_dp_mode and key in (ord('l'), ord('L')):
                opt_scratch_side = "right" if opt_scratch_side == "left" else "left"
            elif key in (10, 13) and player.is_audio_ready:  # Enter key to start play (音声ロード完了後のみ受付け)
                # 決定されたスクラッチサイドに合わせて、キー構成とチャンネルマッピングを再生成する
                #config.scratch_side = opt_scratch_side

                # Determine initial lane mapping based: scratch side
                if not is_dp_mode and opt_scratch_side == "right":
                    channel_to_lane = CHANNEL_TO_LANE_RIGHT.copy()
                    lane_chars = LANE_CHARS_RIGHT.copy()
                else:
                    channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
                    lane_chars = LANE_CHARS_LEFT.copy()
                # Recompute keyboard-to-lane mapping to match the selected scratch side
                KEY_TO_LANE = load_key_config(opt_scratch_side, is_dp=is_dp_mode)
                # Sync player mapping
                player.channel_to_lane = channel_to_lane

                max_lane = 15 if player.chart.get('mode', 'SP') == 'DP' else 7
                # Determine scratch lanes based on mode and side
                if player.chart.get('mode', 'SP') == 'DP':
                    scratch_lanes = {0, max_lane}
                else:
                    scratch_lanes = {7} if opt_scratch_side == "right" else {0}
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
                        # SP: mirror mapping depends on scratch side
                        if opt_scratch_side == "right":
                            # Scratch lane is max_lane (7); playable lanes are 0..max_lane-1
                            lane_map = {lane: (max_lane - 1 - lane) for lane in key_lanes}
                        else:
                            # Scratch lane is 0; playable lanes are 1..max_lane
                            lane_map = {lane: (max_lane + 1 - lane) for lane in key_lanes}
                # Apply lane_map to note channel mapping and lane characters
                if lane_map:
                    # Remap note channels to new lanes for mirrored/random behavior.
                    channel_to_lane = {ch: lane_map.get(lane, lane) for ch, lane in channel_to_lane.items()}
                # Synchronize Player mapping after lane remap
                player.channel_to_lane = channel_to_lane
                # KEY_TO_LANE (keyboard input) remains unchanged to preserve key positions and highlights

                player.auto_scratch = opt_autoscratch
                # EASYとHARDは排他。両方Trueの場合はHARDを優先する。
                player.hard_mode = opt_hard
                player.easy_mode = opt_easy and not opt_hard
                player.show_measure_lines = opt_show_measure_lines
                player.judgement_offset_ms = judgement_offset_ms_config

                # Pass mutable settings dict to on_update for runtime hispeed changes
                mod_keys = load_modifier_keys()
                if 'shift_r' not in mod_keys:
                    # In SP mode, right scratch is lane 7 regardless of side
                    mod_keys['shift_r'] = 7
                # Load configurable hispeed keys from play options
                speedup_key = play_opts.get('speedup_key', 'KEY_UP')
                speeddown_key = play_opts.get('speeddown_key', 'KEY_DOWN')
                settings = {
                    'hispeed': opt_hispeed,
                    'opt_scratch_side': opt_scratch_side,
                    'modifier_keys': mod_keys,
                    'speedup_key': speedup_key,
                    'speeddown_key': speeddown_key,
                }
                on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE, judgement_y_config, settings, lane_chars)
                player.play(on_update=on_update, auto_play=opt_autoplay)
                if player.is_dead:
                    _show_game_over(stdscr, player, quit_key_code)
                running = False

        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
    ae.close()

if __name__ == "__main__":
    curses.wrapper(main)
