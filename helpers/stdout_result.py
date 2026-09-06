import sys


def stdout_result_stats(player):
    """標準出力にプレイ結果・統計情報を表示する。"""
    if not player:
        return

    chart_info = player.chart.get('info', {}) if player.chart else {}
    title = chart_info.get('title', 'Unknown')
    artist = chart_info.get('artist', 'Unknown')

    is_dead = getattr(player, 'is_dead', False)
    hard_mode = getattr(player, 'hard_mode', False)

    events = player.chart.get('events', []) if (player and player.chart) else []
    has_remaining_playable = any(
        ev.get('state', 0) == 0 and ev.get('is_playable', False) and ev.get('ln_state') != 'end'
        for ev in events
    )

    if is_dead:
        status = "GAME OVER"
    elif has_remaining_playable:
        status = "STAGE FAILED (ABORTED)"
    elif hard_mode:
        status = "STAGE CLEAR" if not is_dead else "GAME OVER"
    else:
        status = "STAGE CLEAR" if player.gauge >= 80.0 else "STAGE FAILED"

    max_score = player.total_playable_notes * 2
    ex_rate = (player.ex_score / max_score * 100.0) if max_score > 0 else 0.0

    min_g = getattr(player, 'min_gauge', player.gauge)
    max_g = getattr(player, 'max_gauge', player.gauge)

    print("=== GAME RESULT ===")
    print(f"Title    : {title}")
    print(f"Artist   : {artist}")
    print(f"Status   : {status}")
    print(f"Gauge    : {player.gauge:.1f}%")
    print(f"Min Gauge: {min_g:.1f}%")
    print(f"Max Gauge: {max_g:.1f}%")
    print(f"EX Score : {player.ex_score:d} / {max_score:d} ({ex_rate:.1f}%)")
    print(f"Max Combo: {player.max_combo:d}")
    print(f"PERFECT  : {player.perfect_count:d}")
    print(f"GREAT    : {player.great_count:d}")
    print(f"GOOD     : {player.good_count:d}")
    print(f"BAD      : {player.bad_count:d}")
    print(f"MISS     : {player.miss_count:d}")
    print("===================")
