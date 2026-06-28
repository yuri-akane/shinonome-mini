import curses
import time
import sys
import os
import tomllib
from pathlib import Path
from audio import AudioEngine
from player import Player
from config import load_key_config, load_quit_key, load_scratch_side, load_judgement_config, load_auto_scratch, _load_toml
import config
from on_update import make_on_update
import random
from constants import (
    CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT,
    LANE_CHARS_LEFT, LANE_CHARS_RIGHT,
    KEY_NAMES_DP, KEY_NAMES_RIGHT, KEY_NAMES_LEFT
)

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
            stdscr.addstr(4, 2, f"Loaded: {player.chart['info']['title']}")
            stdscr.addstr(6, 2, "Press 'p' to start MANUAL PLAY")
            stdscr.addstr(7, 2, "Press 'a' to start AUTOPLAY")
            stdscr.addstr(9, 2, f"Press '{config.quit_key_name}' to quit")
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
        opt_show_measure_lines = play_opts.get('show_measure_lines', True)
        opt_hispeed = play_opts.get('hispeed', 1.0)  # Read hispeed from settings
        opt_autoscratch = load_auto_scratch()
    except Exception: #何かひどいことが起きたときのfallback
        opt_autoplay = True
        opt_mirror = False
        opt_random = False
        opt_easy = False
        opt_show_measure_lines = True
        opt_hispeed = 1.0
        opt_scratch_side = "left"
        opt_autoscratch = False

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
            stdscr.addstr(11, 2, f"  [+/-] HS (Hispeed) : {opt_hispeed:.1f}")
            if not is_dp_mode:
                stdscr.addstr(12, 2, f"  [L] SCRATCH SIDE : {opt_scratch_side.upper()}")

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
            elif key == ord('+'):
                opt_hispeed = min(opt_hispeed + 0.2, 10.0)
            elif key == ord('-'):
                opt_hispeed = max(opt_hispeed - 0.2, 0.2)
            elif not is_dp_mode and key in (ord('l'), ord('L')):
                opt_scratch_side = "right" if opt_scratch_side == "left" else "left"
            elif key in (10, 13):  # Enter key to start play
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
                player.easy_mode = opt_easy
                player.show_measure_lines = opt_show_measure_lines
                player.judgement_offset_ms = judgement_offset_ms_config

                # Pass mutable settings dict to on_update for runtime hispeed changes
                settings = {'hispeed': opt_hispeed, 'opt_scratch_side': opt_scratch_side}
                on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE, judgement_y_config, settings, lane_chars)
                player.play(on_update=on_update, auto_play=opt_autoplay)
                running = False

        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
    ae.close()

if __name__ == "__main__":
    curses.wrapper(main)
