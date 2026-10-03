import curses
import time
import sys
import os

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
from helpers.cli_options import parse_args

from player.on_update import make_on_update
from ui.result import show_result
from helpers.sanitizer import sanitize_file_path, sanitize_display_string


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
        print('Example: python3 cnnm.py path/to/song.bms --soundonly')
        sys.exit(1)

    sanitized_path = sanitize_file_path(args.bmsfile)
    if not sanitized_path:
        print(f'Error: Invalid or non-existent BMS file: {args.bmsfile}')
        sys.exit(1)

    ae = AudioEngine()
    channel_to_lane = {}
    player = Player(ae, channel_to_lane)

    print(f'Loading chart: {sanitized_path}')
    try:
        player.load_chart(str(sanitized_path))
    except Exception as e:
        print(f'Error loading chart: {e}')
        ae.close()
        sys.exit(1)

    # Apply force_mode before load_initial_settings
    if args.force_mode and player.chart:
        player.chart['mode'] = args.force_mode
        player.chart['is_dp'] = (args.force_mode in ('10K', '14K'))
        print(f'Mode forced to: {args.force_mode}')

    title = sanitize_display_string(player.chart['info'].get('title', '___')) if player.chart else '___'
    artist = sanitize_display_string(player.chart['info'].get('artist', '___')) if player.chart else '___'
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
    opts = init_settings['opts']

    result = prepare_game_start(player, opts, init_settings['channel_to_lane'])

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

    load_error_msg = None
    if args.bmsfile:
        sanitized_path = sanitize_file_path(args.bmsfile)
        if sanitized_path:
            try:
                player.load_chart(str(sanitized_path))
                player.load_audio_async()  # 音声リソースをバックグラウンドでロード開始
            except Exception as e:
                load_error_msg = f"Error loading chart: {e}"
        else:
            load_error_msg = f"Error: Invalid or non-existent file path ({args.bmsfile})"

    # Load initial settings via helper
    init_settings = load_initial_settings(player, args)
    opts = init_settings['opts']

    channel_to_lane = init_settings['channel_to_lane']
    is_dp = init_settings['is_dp']

    show_advanced_menu = False
    running = True

    # --nomenu: メニューをスキップして即プレイ
    skip_menu = opts.nomenu or (opts.display_mode == 'soundonly')

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
        result = prepare_game_start(player, opts, channel_to_lane)
        channel_to_lane = result['channel_to_lane']
        lane_chars       = result['lane_chars']
        KEY_TO_LANE      = result['KEY_TO_LANE']

        on_update = make_on_update(stdscr, player, KEY_TO_LANE, opts, lane_chars)
        player.play(on_update=on_update, auto_play=opts.autoplay)
        if not opts.autoplay and (player.is_dead or opts.show_result):
            show_result(stdscr, player, opts.quit_key_code, display_mode=opts.display_mode)
        ae.close()
        return player, opts.stdout_result, True

    played = False
    while running:
        stdscr.erase()
        safe_addstr(stdscr, 0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)

        if player.chart:
            title = sanitize_display_string(player.chart['info'].get('title', '___'))
            artist = sanitize_display_string(player.chart['info'].get('artist', '___'))
            chart_mode = player.chart.get('mode', '7K').upper()
            is_dp_mode = (chart_mode in ('10K', '14K'))
            has_scratch = (chart_mode in ('5K', '7K', '10K', '14K'))
            safe_addstr(stdscr, 1, 2, f"Song: {title} / Artist: {artist}")
            safe_addstr(stdscr, 2, 2, f"MODE: {chart_mode} ({'DP' if is_dp_mode else 'SP'})")

            # ロード状態の表示
            if player.audio.is_loading:
                loaded, total = player.audio.loading_progress
                safe_addstr(stdscr, 3, 2, f"Loading audio... ({loaded}/{total})")
            else:
                safe_addstr(stdscr, 3, 2, "Audio ready.                          ")

            if show_advanced_menu:
                safe_addstr(stdscr, 4, 2, "=== ADVANCED OPTIONS ===", curses.A_BOLD)
                row = 5
                safe_addstr(stdscr, row, 2, f"  [1] SHOW RESULT   : {'ON' if opts.show_result else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [2] DISPLAY MODE  : {opts.display_mode.upper()}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [3] STDOUT RESULT : {'ON' if opts.stdout_result else 'OFF'}"); row += 2

                safe_addstr(stdscr, row, 2, "Press key [1/2/3] to toggle option."); row += 2
                safe_addstr(stdscr, row, 2, "Press [F7] to return to Main Options."); row += 1
                safe_addstr(stdscr, row, 2, f"Press [{opts.quit_key_name}] to Quit")
            else:
                # プレイオプション設定の表示
                safe_addstr(stdscr, 4, 2, "=== PLAY OPTIONS ===")
                row = 5
                safe_addstr(stdscr, row, 2, f"  [A] AUTO PLAY    : {'ON' if opts.autoplay else 'OFF'}"); row += 1
                if has_scratch:
                    safe_addstr(stdscr, row, 2, f"  [S] AUTO SCRATCH : {'ON' if opts.autoscratch else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [M] MIRROR       : {'ON' if opts.mirror else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [R] RANDOM       : {'ON' if opts.random else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [E] EASY         : {'ON' if opts.easy else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [H] HARD GAUGE   : {'ON' if opts.hard else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [O] SHOW MEASURES: {'ON' if opts.show_measure_lines else 'OFF'}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [keyup/down] HS (Hispeed) : {opts.hispeed:.1f}"); row += 1
                if not is_dp_mode and has_scratch:
                    safe_addstr(stdscr, row, 2, f"  [L] SCRATCH SIDE : {opts.scratch_side.upper()}"); row += 1
                safe_addstr(stdscr, row, 2, f"  [$] SOLID GAUGE  : {'ON' if opts.solid else 'OFF'}"); row += 2

                toggle_keys = "A"
                if has_scratch:
                    toggle_keys += "/S"
                toggle_keys += "/M/R/E/H/O"
                if not is_dp_mode and has_scratch:
                    toggle_keys += "/L"
                toggle_keys += "/$"

                safe_addstr(stdscr, row, 2, f"Press key [{toggle_keys}] to toggle option."); row += 1
                safe_addstr(stdscr, row, 2, "Press [F7] for Advanced Options."); row += 2
                if player.is_audio_ready:
                    safe_addstr(stdscr, row, 2, "Press [Enter] to START PLAY"); row += 1
                else:
                    safe_addstr(stdscr, row, 2, "[Enter] will be available after audio loads"); row += 1
                safe_addstr(stdscr, row, 2, f"Press [{opts.quit_key_name}] to Quit")
        else:
            if load_error_msg:
                safe_addstr(stdscr, 2, 2, load_error_msg, curses.A_BOLD)
            else:
                safe_addstr(stdscr, 2, 2, "Please specify a BMS file as an argument.")
            safe_addstr(stdscr, 3, 2, "Example: python3 main.py path/to/song.bms")
            safe_addstr(stdscr, 5, 2, f"Press [{opts.quit_key_name}] to Quit")

        stdscr.refresh()

        key = stdscr.getch()
        if key == opts.quit_key_code:
            running = False
        elif key in (curses.KEY_F7, getattr(curses, 'KEY_F7', 271)):  # F7 キーでAdvanced画面トグル
            show_advanced_menu = not show_advanced_menu
        elif player.chart:
            if key in (10, 13) and player.is_audio_ready:  # Enter key to start play
                result = prepare_game_start(player, opts, channel_to_lane)
                channel_to_lane = result['channel_to_lane']
                lane_chars = result['lane_chars']
                KEY_TO_LANE = result['KEY_TO_LANE']

                on_update = make_on_update(stdscr, player, KEY_TO_LANE, opts, lane_chars)
                player.play(on_update=on_update, auto_play=opts.autoplay)
                if not opts.autoplay and (player.is_dead or opts.show_result):
                    show_result(stdscr, player, opts.quit_key_code, display_mode=opts.display_mode)
                played = True
                running = False
            elif show_advanced_menu:
                if key == ord('1'):
                    opts.show_result = not opts.show_result
                elif key == ord('2'):
                    opts.toggle_display_mode()
                elif key == ord('3'):
                    opts.stdout_result = not opts.stdout_result
            else:
                chart_mode = player.chart.get('mode', '7K').upper()
                is_dp_mode = (chart_mode in ('10K', '14K'))
                has_scratch = (chart_mode in ('5K', '7K', '10K', '14K'))
                if key in (ord('a'), ord('A')):
                    opts.autoplay = not opts.autoplay
                elif has_scratch and key in (ord('s'), ord('S')):
                    opts.autoscratch = not opts.autoscratch
                elif key in (ord('m'), ord('M')):
                    opts.mirror = not opts.mirror
                elif key in (ord('r'), ord('R')):
                    opts.random = not opts.random
                elif key in (ord('e'), ord('E')):
                    opts.easy = not opts.easy
                    if opts.easy:
                        opts.hard = False  # EASYとHARDは排他
                elif key in (ord('h'), ord('H')):
                    opts.hard = not opts.hard
                    if opts.hard:
                        opts.easy = False  # EASYとHARDは排他
                elif key == ord('$'):
                    opts.solid = not opts.solid
                elif key in (ord('o'), ord('O')):
                    opts.show_measure_lines = not opts.show_measure_lines
                elif key == opts.speedup_code:
                    opts.hispeed = min(opts.hispeed + 0.2, 100.0)
                elif key == opts.speeddown_code:
                    opts.hispeed = max(opts.hispeed - 0.2, 0.2)
                elif not is_dp_mode and has_scratch and key in (ord('l'), ord('L')):
                    opts.scratch_side = "right" if opts.scratch_side == "left" else "left"

        time.sleep(0.05) #ここのsleepはメニュー画面での話なのでこれ(20FPS)で十分
    ae.close()
    return player, opts.stdout_result, played

from helpers.options import load_options

if __name__ == "__main__":
    args = parse_args()
    opts = load_options(args)

    if opts.display_mode in ('soundonly', 'none'):
        run_soundonly(args)
    else:
        res = curses.wrapper(main, args)
        if res:
            player, opt_stdout_result, played = res
            if played and opt_stdout_result and player:
                from helpers.stdout_result import stdout_result_stats
                stdout_result_stats(player)
