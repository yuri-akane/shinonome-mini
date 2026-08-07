import curses
import time
import sys
import os
import tomllib
from pathlib import Path
from audio import AudioEngine
from player import Player
# Import new helper modules
from helpers.load_initial_settings import load_initial_settings
from helpers.prepare_game_start import prepare_game_start
import config
from on_update import make_on_update
import random
from constants import (
    CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT,
    LANE_CHARS_LEFT, LANE_CHARS_RIGHT,
    KEY_NAMES_DP, KEY_NAMES_RIGHT, KEY_NAMES_LEFT
)
# Added imports for missing functions used in main()
from config import load_key_config, load_modifier_keys

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

    # Load initial settings via helper
    init_settings = load_initial_settings(player)

    opt_scratch_side = init_settings['opt_scratch_side']
    channel_to_lane = init_settings['channel_to_lane']
    lane_chars = init_settings['lane_chars']
    is_dp = init_settings['is_dp']
    KEY_TO_LANE = init_settings['KEY_TO_LANE']
    quit_key_code = init_settings['quit_key_code']
    judgement_y_config = init_settings['judgement_y_config']
    judgement_offset_ms_config = init_settings['judgement_offset_ms_config']

    opt_autoplay = init_settings['opt_autoplay']
    opt_mirror = init_settings['opt_mirror']
    opt_random = init_settings['opt_random']
    opt_easy = init_settings['opt_easy']
    opt_hard = init_settings['opt_hard']
    opt_solid = init_settings['opt_solid']
    opt_show_measure_lines = init_settings['opt_show_measure_lines']
    opt_show_ln_end_head = init_settings.get('opt_show_ln_end_head', True)
    opt_hispeed = init_settings['opt_hispeed']
    opt_autoscratch = init_settings['opt_autoscratch']

    speedup_code = init_settings.get('speedup_code')
    speeddown_code = init_settings.get('speeddown_code')

    # Expose play options for later use
    play_opts = init_settings.get('play_opts', {})

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
                stdscr.addstr(14, 2, f"  [$] SOLID GAUGE  : {'ON' if opt_solid else 'OFF'}")
            else:
                stdscr.addstr(13, 2, f"  [$] SOLID GAUGE  : {'ON' if opt_solid else 'OFF'}")
            stdscr.addstr(16, 2, "Press key [A/S/M/R/E/H/O" + ("" if is_dp_mode else "/L") + "/$] to toggle option.")
            if player.is_audio_ready:
                stdscr.addstr(18, 2, "Press [Enter] to START PLAY")
            else:
                stdscr.addstr(18, 2, "[Enter] will be available after audio loads")
            stdscr.addstr(19, 2, f"Press [{config.quit_key_name}] to Quit")
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
            elif key == ord('$'):
                opt_solid = not opt_solid
            elif key in (ord('o'), ord('O')):
                opt_show_measure_lines = not opt_show_measure_lines
            elif key == speedup_code:
                opt_hispeed = min(opt_hispeed + 0.2, 100.0)
            elif key == speeddown_code:
                opt_hispeed = max(opt_hispeed - 0.2, 0.2)
            elif not is_dp_mode and key in (ord('l'), ord('L')):
                opt_scratch_side = "right" if opt_scratch_side == "left" else "left"
            elif key in (10, 13) and player.is_audio_ready:  # Enter key to start play (音声ロード完了後のみ受付け)
                # Prepare game start using helper
                result = prepare_game_start(player,
                                            opt_scratch_side,
                                            channel_to_lane,
                                            lane_chars,
                                            KEY_TO_LANE,
                                            judgement_y_config,
                                            judgement_offset_ms_config,
                                            opt_autoscratch,
                                            opt_hard,
                                            opt_easy,
                                            opt_solid,
                                            opt_show_measure_lines,
                                            opt_show_ln_end_head,
                                            opt_hispeed,
                                            speedup_code,
                                            speeddown_code,
                                            play_opts,
                                            opt_mirror,   # new argument
                                            opt_random)   # new argument
                channel_to_lane = result['channel_to_lane']
                lane_chars = result['lane_chars']
                KEY_TO_LANE = result['KEY_TO_LANE']
                settings = result['settings']

                on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE,
                                          judgement_y_config, settings, lane_chars)
                player.play(on_update=on_update, auto_play=opt_autoplay)
                if player.is_dead:
                    _show_game_over(stdscr, player, quit_key_code)
                running = False

        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
    ae.close()

if __name__ == "__main__":
    curses.wrapper(main)
