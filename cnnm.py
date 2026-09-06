import curses
import time
import sys
import os
import argparse
#import tomllib
#from pathlib import Path

# Windows では msvcrt を使い、POSIX では select をそのまま使用する
try:
    import msvcrt # Windows
except ImportError:
    msvcrt = None
    import select # POSIX

from audio.core import AudioEngine
from player.core import Player
from helpers.load_initial_settings import load_initial_settings
from helpers.prepare_game_start import prepare_game_start
import config
from on_update import make_on_update
from ui.result import show_result
#import random
#from constants import (
#    CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT,
#    LANE_CHARS_LEFT, LANE_CHARS_RIGHT,
#    KEY_NAMES_DP, KEY_NAMES_RIGHT, KEY_NAMES_LEFT
#)
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
    parser.add_argument(      '--stats',       dest='stats',        action='store_true', help='Output performance stats to stdout upon song completion')

    # --- Display mode (mutually exclusive) ---
    disp = parser.add_mutually_exclusive_group()
    disp.add_argument('--soundonly', dest='soundonly', action='store_true', help='Audio-only mode (no UI, forces autoplay)')
    disp.add_argument('--none',      dest='none',      action='store_true', help='No UI mode (same as --soundonly)')
    disp.add_argument('--tiny',      dest='tiny',      action='store_true', help='Tiny display mode (1-char width, minimal UI)')
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
    if args.soundonly or args.none:
        args.display_mode = 'soundonly'
        args.cli_display_mode_set = True
    elif args.tiny:
        args.display_mode = 'tiny'
        args.cli_display_mode_set = True
    elif args.mini:
        args.display_mode = 'mini'
        args.cli_display_mode_set = True
    else:
        from config import load_display_mode
        args.display_mode = load_display_mode()
        args.cli_display_mode_set = False

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

    # soundonly / none implies autoplay
    if args.display_mode in ('soundonly', 'none'):
        args.autoplay = True

    return args


def safe_addstr(stdscr, y: int, x: int, text: str, attr=curses.A_NORMAL):
    """Safely print text to stdscr without raising curses.error when clipping boundaries."""
    try:
        max_y, max_x = stdscr.getmaxyx()
        if 0 <= y < max_y and 0 <= x < max_x:
            stdscr.addstr(y, x, text[:max_x - x], attr)
    except curses.error:
        pass


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

    print('Playing... (Press Enter to stop)')

    # Dummy on_update for quit_key handling
    def dummy_on_update(current_time, events, event_index, initial_bpm,
                        resolution, auto_play):
        """
        非ブロッキングで入力を確認し、行単位で読み込んだら停止。
        Windows では msvcrt.kbhit()/getwch() を使用し、POSIX では
        select.select([sys.stdin], [], [], 0) をそのまま利用する。
        """
        if msvcrt is not None:          # Windows
            if msvcrt.kbhit():
                ch = msvcrt.getwch()    # Unicode 文字を取得
                # CR / LF が押されたら停止
                if ch in ('\r', '\n'):
                    player.is_playing = False
        else:                            # POSIX (Linux/macOS)
            if select.select([sys.stdin], [], [], 0)[0]:
                # readline() はバッファにある行全体（改行付き）を返すので、
                # その時点で「Enter」が押されたことになる。
                sys.stdin.readline()
                player.is_playing = False

    player.play(on_update=dummy_on_update, auto_play=True)
    ae.close()
    if init_settings.get('opt_stdout_result', False):
        from helpers.stdout_result import stdout_result_stats
        stdout_result_stats(player)

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
    opt_show_result = init_settings.get('opt_show_result', False)
    opt_stdout_result = init_settings.get('opt_stdout_result', False)
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
            safe_addstr(stdscr, 0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
            safe_addstr(stdscr, 2, 2, f"Loading audio... ({loaded}/{total})")
            safe_addstr(stdscr, 3, 2, "Starting automatically after load...")
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
            display_mode=display_mode,
        )
        channel_to_lane = result['channel_to_lane']
        lane_chars       = result['lane_chars']
        KEY_TO_LANE      = result['KEY_TO_LANE']
        settings         = result['settings']

        on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE,
                                  judgement_y_config, settings, lane_chars,
                                  display_mode=display_mode)
        player.play(on_update=on_update, auto_play=opt_autoplay)
        if not opt_autoplay and (player.is_dead or opt_show_result):
            show_result(stdscr, player, quit_key_code, display_mode=display_mode)
        ae.close()
        return player, opt_stdout_result, True

    played = False
    while running:
        stdscr.erase()
        safe_addstr(stdscr, 0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)

        if player.chart:
            chart_mode = player.chart.get('mode', '7K').upper()
            is_dp_mode = (chart_mode in ('10K', '14K'))
            has_scratch = (chart_mode in ('5K', '7K', '10K', '14K'))
            safe_addstr(stdscr, 1, 2, f"Song: {player.chart['info'].get('title', 'Unknown')} / Artist: {player.chart['info'].get('artist', 'Unknown')}")
            safe_addstr(stdscr, 2, 2, f"MODE: {chart_mode} ({'DP' if is_dp_mode else 'SP'})")

            # ロード状態の表示
            if player.audio.is_loading:
                loaded, total = player.audio.loading_progress
                safe_addstr(stdscr, 3, 2, f"Loading audio... ({loaded}/{total})")
            else:
                safe_addstr(stdscr, 3, 2, "Audio ready.                          ")

            # プレイオプション設定の表示
            safe_addstr(stdscr, 4, 2, "=== PLAY OPTIONS ===")
            row = 5
            safe_addstr(stdscr, row, 2, f"  [A] AUTO PLAY    : {'ON' if opt_autoplay else 'OFF'}"); row += 1
            if has_scratch:
                safe_addstr(stdscr, row, 2, f"  [S] AUTO SCRATCH : {'ON' if opt_autoscratch else 'OFF'}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [M] MIRROR       : {'ON' if opt_mirror else 'OFF'}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [R] RANDOM       : {'ON' if opt_random else 'OFF'}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [E] EASY         : {'ON' if opt_easy else 'OFF'}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [H] HARD GAUGE   : {'ON' if opt_hard else 'OFF'}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [O] SHOW MEASURES: {'ON' if opt_show_measure_lines else 'OFF'}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [keyup/down] HS (Hispeed) : {opt_hispeed:.1f}"); row += 1
            if not is_dp_mode and has_scratch:
                safe_addstr(stdscr, row, 2, f"  [L] SCRATCH SIDE : {opt_scratch_side.upper()}"); row += 1
            safe_addstr(stdscr, row, 2, f"  [$] SOLID GAUGE  : {'ON' if opt_solid else 'OFF'}"); row += 2

            toggle_keys = "A"
            if has_scratch:
                toggle_keys += "/S"
            toggle_keys += "/M/R/E/H/O"
            if not is_dp_mode and has_scratch:
                toggle_keys += "/L"
            toggle_keys += "/$"

            safe_addstr(stdscr, row, 2, f"Press key [{toggle_keys}] to toggle option."); row += 2
            if player.is_audio_ready:
                safe_addstr(stdscr, row, 2, "Press [Enter] to START PLAY"); row += 1
            else:
                safe_addstr(stdscr, row, 2, "[Enter] will be available after audio loads"); row += 1
            safe_addstr(stdscr, row, 2, f"Press [{config.quit_key_name}] to Quit")
        else:
            safe_addstr(stdscr, 2, 2, "Please specify a BMS file as an argument.")
            safe_addstr(stdscr, 3, 2, "Example: python3 main.py path/to/song.bms")
            safe_addstr(stdscr, 5, 2, f"Press [{config.quit_key_name}] to Quit")

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
                                            opt_random,   # new argument
                                            display_mode=display_mode)
                channel_to_lane = result['channel_to_lane']
                lane_chars = result['lane_chars']
                KEY_TO_LANE = result['KEY_TO_LANE']
                settings = result['settings']

                on_update = make_on_update(stdscr, player, quit_key_code, KEY_TO_LANE,
                                          judgement_y_config, settings, lane_chars,
                                          display_mode=display_mode)
                player.play(on_update=on_update, auto_play=opt_autoplay)
                if not opt_autoplay and (player.is_dead or opt_show_result):
                    show_result(stdscr, player, quit_key_code, display_mode=display_mode)
                played = True
                running = False

        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
    ae.close()
    return player, opt_stdout_result, played

if __name__ == "__main__":
    args = parse_args()

    if args.display_mode == 'soundonly':
        run_soundonly(args)
    else:
        res = curses.wrapper(main, args)
        if res:
            player, opt_stdout_result, played = res
            if played and opt_stdout_result and player:
                from helpers.stdout_result import stdout_result_stats
                stdout_result_stats(player)
