import curses
import time
import config


def show_result(stdscr, player, quit_key_code: int, display_mode: str = 'mini'):
    """ゲームオーバーまたは曲終了時のリザルト画面を表示する。
    任意キーを受け取るまでブロックする。
    """
    try:
        curses.curs_set(0)
        stdscr.nodelay(False)
    except curses.error:
        pass
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()

    is_dead = getattr(player, 'is_dead', False)
    hard_mode = getattr(player, 'hard_mode', False)

    # 叩かれていない（処理されていない）ノーツが残っているかチェック
    events = player.chart.get('events', []) if (player and player.chart) else []
    has_remaining_playable = any(
        ev.get('state', 0) == 0 and ev.get('is_playable', False) and ev.get('ln_state') != 'end'
        for ev in events
    )

    if is_dead or has_remaining_playable:
        is_clear = False
    elif hard_mode:
        is_clear = not is_dead
    else:
        is_clear = (player.gauge >= 80.0)

    if display_mode == 'tiny':
        box_w = 20
        box_h = 10
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

        if is_dead:
            title = "GAME OVER"
            sub = "HARD 0%"
        elif is_clear:
            title = "STAGE CLEAR"
            sub = f"GAUGE {player.gauge:.1f}%"
        else:
            title = "FAILED"
            sub = f"GAUGE {player.gauge:.1f}%"

        pr(1, (box_w - len(title)) // 2, title, curses.A_BOLD | curses.A_STANDOUT)
        pr(2, (box_w - len(sub)) // 2, sub)

        pr(3, 2, f"P:{player.perfect_count:4d}  G:{player.great_count:4d}")
        pr(4, 2, f"g:{player.good_count:4d}  B:{player.bad_count:4d}")
        pr(5, 2, f"M:{player.miss_count:4d}")

        max_score = player.total_playable_notes * 2
        pr(6, 2, f"EX: {player.ex_score:4d}/{max_score:4d}")
        pr(7, 2, f"MAX:{player.max_combo:4d}")

        footer = f"[{config.quit_key_name}] Quit"
        pr(8, (box_w - len(footer)) // 2, footer, curses.A_DIM)
    else:
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

        if is_dead:
            title = "G A M E   O V E R"
            sub = "~  Hard Gauge reached 0%  ~"
        elif is_clear:
            title = "S T A G E   C L E A R"
            sub = f"~  Song Completed (Gauge: {player.gauge:.1f}%)  ~"
        else:
            title = "S T A G E   F A I L E D"
            sub = f"~  Failed (Gauge: {player.gauge:.1f}%)  ~"

        pr(2, (box_w - len(title)) // 2, title, curses.A_BOLD | curses.A_STANDOUT)
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

        min_g = getattr(player, 'min_gauge', player.gauge)
        max_g = getattr(player, 'max_gauge', player.gauge)
        pr(15, 5, f"MIN GAUGE: {min_g:5.1f}% / MAX GAUGE: {max_g:5.1f}%")

        footer = f"Press [{config.quit_key_name}] to Quit"
        pr(16, (box_w - len(footer)) // 2, footer, curses.A_DIM)

    stdscr.refresh()
    while True:
        time.sleep(0.05)
        key = stdscr.getch()
        if key == quit_key_code:
            break
        else:
            continue
    try:
        stdscr.nodelay(True)
    except curses.error:
        pass
