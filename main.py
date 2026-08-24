import curses
import time
import sys
import os
import argparse
import tomllib
from pathlib import Path
from audio.core import AudioEngine
from player.core import Player
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


def _normalize_mode(raw: str) -> str:
    """--mode / --mode-hint の値を内部形式（'7K'等）に正規化する。

    Examples:
        'beat-7k'  -> '7K'
        '7k'       -> '7K'
        'beat-14k' -> '14K'
    """
    s = raw.strip().lower()
    # bmson 互換形式: beat-Xk
    if s.startswith('beat-'):
        s = s[len('beat-'):]
    # '4k' -> '4K' 形式
    if s.endswith('k'):
        return s[:-1].upper() + 'K'
    return s.upper()


VALID_MODES = {'4K', '5K', '6K', '7K', '9K', '10K', '14K'}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.  Key attributes:

        bmsfile (str|None)      : path to the BMS/bmson file
        autoplay (bool)         : --auto / -a
        mirror (bool)           : --mirror / -m
        random (bool)           : --random / -r
        easy (bool)             : --easy / -e
        hard (bool)             : --hard / -h
        solid (bool)            : --solid
        autoscratch (bool)      : --autoscratch / -s
        display_mode (str)      : 'mini' | 'tiny' | 'soundonly'  (default 'mini')
        nomenu (bool)           : --nomenu
        force_mode (str|None)   : normalized game mode string, e.g. '7K'
    """
    parser = argparse.ArgumentParser(
        description='Shinonome-Mini -- Minimal Console BMS Player',
        add_help=False,  # -h を --hard に割り当てるためデフォルトの -h/--help を無効化
    )
    parser.add_argument('--help', action='help', default=argparse.SUPPRESS,
                        help='Show this help message and exit')

    # Positional: BMS file (optional so that the player can still show usage)
    parser.add_argument(
        'bmsfile',
        nargs='?',
        default=None,
        metavar='FILE',
        help='Path to a BMS/bmson file',
    )

    # --- Play option flags ---
    parser.add_argument('-a', '--auto',        dest='autoplay',     action='store_true', help='Force AUTO PLAY on')
    parser.add_argument('-m', '--mirror',      dest='mirror',       action='store_true', help='Force MIRROR on')
    parser.add_argument('-r', '--random',      dest='random',       action='store_true', help='Force RANDOM on')
    parser.add_argument('-e', '--easy',        dest='easy',         action='store_true', help='Force EASY gauge on')
    parser.add_argument('-h', '--hard',        dest='hard',         action='store_true', help='Force HARD gauge on')
    parser.add_argument(      '--solid',       dest='solid',        action='store_true', help='Force SOLID gauge on')
    parser.add_argument('-s', '--autoscratch', dest='autoscratch',  action='store_true', help='Force AUTO SCRATCH on')

    # --- Display mode (mutually exclusive) ---
    disp = parser.add_mutually_exclusive_group()
    disp.add_argument('--soundonly', dest='soundonly', action='store_true', help='Audio-only mode (no UI, forces autoplay)')
    disp.add_argument('--tiny',      dest='tiny',      action='store_true', help='Tiny display mode (placeholder, same as --mini for now)')
    disp.add_argument('--mini',      dest='mini',      action='store_true', help='Normal display mode (default)')

    # --- Menu control ---
    parser.add_argument('--nomenu', dest='nomenu', action='store_true', help='Skip menu and start playing immediately')

    # --- Game mode override ---
    # Both --mode-hint=beat-7k (bmson-compatible) and --mode=7k (shorthand) are supported.
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--mode-hint',
        dest='mode_hint',
        metavar='HINT',
        default=None,
        help='Game mode hint (bmson-compatible, e.g. beat-7k)',
    )
    mode_group.add_argument(
        '--mode',
        dest='mode',
        metavar='MODE',
        default=None,
        help='Game mode override (e.g. 7k, 14k)',
    )

    args = parser.parse_args()

    # Derive display_mode string
    if args.soundonly:
        args.display_mode = 'soundonly'
    elif args.tiny:
        args.display_mode = 'tiny'
    else:
        args.display_mode = 'mini'

    # Derive force_mode
    raw_mode = args.mode_hint or args.mode
    if raw_mode:
        normalized = _normalize_mode(raw_mode)
        if normalized in VALID_MODES:
            args.force_mode = normalized
        else:
            print(f"Warning: Unknown mode '{raw_mode}', ignoring --mode / --mode-hint", file=sys.stderr)
            args.force_mode = None
    else:
        args.force_mode = None

    # soundonly implies autoplay
    if args.display_mode == 'soundonly':
        args.autoplay = True

    return args


def run_soundonly(args):
    """--soundonly 時のエントリーポイント。curses なしで音声のみ再生する。"""
    if not args.bmsfile:
        print('Error: Please specify a BMS file as an argument.')
        print('Example: python3 main.py path/to/song.bms --soundonly')
        sys.exit(1)

    ae = AudioEngine()
    channel_to_lane = {}
    player = Player(ae, channel_to_lane)

    print(f'Loading chart: {args.bmsfile}')
    try:
        player.load_chart(args.bmsfile)
    except Exception as e:
        print(f'Error loading chart: {e}')
        ae.close()
        sys.exit(1)

    # Apply force_mode before load_initial_settings
    if args.force_mode and player.chart:
        player.chart['mode'] = args.force_mode
        player.chart['is_dp'] = (args.force_mode in ('10K', '14K'))
        print(f'Mode forced to: {args.force_mode}')

    title = player.chart['info'].get('title', 'Unknown') if player.chart else 'Unknown'
    artist = player.chart['info'].get('artist', 'Unknown') if player.chart else 'Unknown'
    print(f'Title : {title}')
    print(f'Artist: {artist}')

    print('Loading audio...', end='', flush=True)
    player.load_audio_async()
    # Wait for audio to finish loading
    while player.audio.is_loading:
        time.sleep(0.1)
        loaded, total = player.audio.loading_progress
        print(f'\rLoading audio... ({loaded}/{total})    ', end='', flush=True)
    print('\rAudio ready.                      ')

    init_settings = load_initial_settings(player, args)

    from helpers.prepare_game_start import prepare_game_start
    from config import load_judgement_config
    judgement_y_config, judgement_offset_ms_config = load_judgement_config()
    opt_scratch_side  = init_settings['opt_scratch_side']
    channel_to_lane   = init_settings['channel_to_lane']
    lane_chars        = init_settings['lane_chars']
    KEY_TO_LANE       = init_settings['KEY_TO_LANE']
    play_opts         = init_settings.get('play_opts', {})
    speedup_code      = init_settings.get('speedup_code')
    speeddown_code    = init_settings.get('speeddown_code')

    result = prepare_game_start(
        player,
        opt_scratch_side,
        channel_to_lane,
        lane_chars,
        KEY_TO_LANE,
        judgement_y_config,
        judgement_offset_ms_config,
        init_settings['opt_autoscratch'],
        init_settings['opt_hard'],
        init_settings['opt_easy'],
        init_settings['opt_solid'],
        init_settings['opt_show_measure_lines'],
        init_settings['opt_show_ln_end_head'],
        init_settings['opt_hispeed'],
        speedup_code,
        speeddown_code,
        play_opts,
        init_settings['opt_mirror'],
        init_settings['opt_random'],
    )

    print('Playing... (Press Ctrl+C to stop)')
    try:
        player.play(on_update=None, auto_play=True)
    except KeyboardInterrupt:
        pass
    finally:
        ae.close()

    print('\nDone.')

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


def main(stdscr, args):
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

    # 引数からBMSファイルパスを取得（parse_args() で処理済み）
    if args.bmsfile:
        try:
            player.load_chart(args.bmsfile)
            player.load_audio_async()  # 音声リソースをバックグラウンドでロード開始
        except Exception as e:
            stdscr.addstr(4, 2, f"Error: {e}")
    else:
        stdscr.addstr(4, 2, "Please specify a BMS file as an argument.")
        stdscr.addstr(5, 2, "Example: python3 main.py path/to/song.bms")

    # Load initial settings via helper
    init_settings = load_initial_settings(player, args)

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
    # --nomenu: メニューをスキップして即プレイ
    skip_menu = args.nomenu or (args.display_mode == 'soundonly')

    # 表示モードのメモ（将来の --tiny 実装用）
    display_mode = args.display_mode  # 'mini' | 'tiny' | 'soundonly'

    # --nomenu: 音声ロード完了まで待って即プレイ
    if skip_menu and player.chart:
        # 音声ロード完了待機
        while not player.is_audio_ready:
            stdscr.erase()
            loaded, total = player.audio.loading_progress
            stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
            stdscr.addstr(2, 2, f"Loading audio... ({loaded}/{total})")
            stdscr.addstr(3, 2, "Starting automatically after load...")
            stdscr.refresh()
            time.sleep(0.1)

        # 即プレイ
        result = prepare_game_start(
            player,
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
            opt_mirror,
            opt_random,
        )
        channel_to_lane = result['channel_to_lane']
        lane_chars       = result['lane_chars']
        KEY_TO_LANE      = result['KEY_TO_LANE']
        settings         = result['settings']

        on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE,
                                  judgement_y_config, settings, lane_chars)
        player.play(on_update=on_update, auto_play=opt_autoplay)
        if player.is_dead:
            _show_game_over(stdscr, player, quit_key_code)
        ae.close()
        return

    while running:
        stdscr.erase()
        stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)

        if player.chart:
            chart_mode = player.chart.get('mode', '7K').upper()
            is_dp_mode = (chart_mode in ('10K', '14K'))
            has_scratch = (chart_mode in ('5K', '7K', '10K', '14K'))
            stdscr.addstr(1, 2, f"Song: {player.chart['info'].get('title', 'Unknown')} / Artist: {player.chart['info'].get('artist', 'Unknown')}")
            stdscr.addstr(2, 2, f"MODE: {chart_mode} ({'DP' if is_dp_mode else 'SP'})")

            # ロード状態の表示
            if player.audio.is_loading:
                loaded, total = player.audio.loading_progress
                stdscr.addstr(3, 2, f"Loading audio... ({loaded}/{total})")
            else:
                stdscr.addstr(3, 2, "Audio ready.                          ")

            # プレイオプション設定の表示
            stdscr.addstr(4, 2, "=== PLAY OPTIONS ===")
            row = 5
            stdscr.addstr(row, 2, f"  [A] AUTO PLAY    : {'ON' if opt_autoplay else 'OFF'}"); row += 1
            if has_scratch:
                stdscr.addstr(row, 2, f"  [S] AUTO SCRATCH : {'ON' if opt_autoscratch else 'OFF'}"); row += 1
            stdscr.addstr(row, 2, f"  [M] MIRROR       : {'ON' if opt_mirror else 'OFF'}"); row += 1
            stdscr.addstr(row, 2, f"  [R] RANDOM       : {'ON' if opt_random else 'OFF'}"); row += 1
            stdscr.addstr(row, 2, f"  [E] EASY         : {'ON' if opt_easy else 'OFF'}"); row += 1
            stdscr.addstr(row, 2, f"  [H] HARD GAUGE   : {'ON' if opt_hard else 'OFF'}"); row += 1
            stdscr.addstr(row, 2, f"  [O] SHOW MEASURES: {'ON' if opt_show_measure_lines else 'OFF'}"); row += 1
            stdscr.addstr(row, 2, f"  [keyup/down] HS (Hispeed) : {opt_hispeed:.1f}"); row += 1
            if not is_dp_mode and has_scratch:
                stdscr.addstr(row, 2, f"  [L] SCRATCH SIDE : {opt_scratch_side.upper()}"); row += 1
            stdscr.addstr(row, 2, f"  [$] SOLID GAUGE  : {'ON' if opt_solid else 'OFF'}"); row += 2

            toggle_keys = "A"
            if has_scratch:
                toggle_keys += "/S"
            toggle_keys += "/M/R/E/H/O"
            if not is_dp_mode and has_scratch:
                toggle_keys += "/L"
            toggle_keys += "/$"

            stdscr.addstr(row, 2, f"Press key [{toggle_keys}] to toggle option."); row += 2
            if player.is_audio_ready:
                stdscr.addstr(row, 2, "Press [Enter] to START PLAY"); row += 1
            else:
                stdscr.addstr(row, 2, "[Enter] will be available after audio loads"); row += 1
            stdscr.addstr(row, 2, f"Press [{config.quit_key_name}] to Quit")
        else:
            stdscr.addstr(2, 2, "Please specify a BMS file as an argument.")
            stdscr.addstr(3, 2, "Example: python3 main.py path/to/song.bms")
            stdscr.addstr(5, 2, f"Press [{config.quit_key_name}] to Quit")

        stdscr.refresh()

        key = stdscr.getch()
        if key == quit_key_code:
            running = False
        elif player.chart:
            chart_mode = player.chart.get('mode', '7K').upper()
            is_dp_mode = (chart_mode in ('10K', '14K'))
            has_scratch = (chart_mode in ('5K', '7K', '10K', '14K'))
            if key in (ord('a'), ord('A')):
                opt_autoplay = not opt_autoplay
            elif has_scratch and key in (ord('s'), ord('S')):
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
            elif not is_dp_mode and has_scratch and key in (ord('l'), ord('L')):
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
    args = parse_args()

    if args.display_mode == 'soundonly':
        run_soundonly(args)
    else:
        curses.wrapper(main, args)
