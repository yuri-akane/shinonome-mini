from typing import Any

#TODO: lazy import or delete it from bms[on]parser
from timing import BpmTimeline, stop_seconds


def _playable_channels() -> set[str]:
    """Return the set of channel identifiers that are considered playable for 01ch duplicate removal."""
    return {
        "11", "12", "13", "14", "15", "16", "17", "18", "19",
        "21", "22", "23", "24", "25", "26", "27", "28", "29",
        "51", "52", "53", "54", "55", "56", "57", "58", "59",
        "61", "62", "63", "64", "65", "66", "67", "68", "69"
    }


def get_event_priority(ev: dict[str, Any]) -> float:
    """
    beat順およびチャンネルプライオリティ順にソートする
    BPM変更は同じbeatにある音符より先に評価し、STOPは音符が再生された後に停止するため音符より後に評価するべき
    Return a numeric priority for sorting events.
    Lower values are sorted first.

    Priority rules (from the original parser):
        * BPM/SCROLL changes (channels 03, 08 or SC) – priority 0
        * Visual measure lines – priority 1.5
        * STOP events – priority 3
        * All other note / sound channels – priority 2
    """
    ch = ev.get("channel", "XX")
    if ch in ("03", "08") or ch == "SC":
        return 0.0
    if ch == "measure_line":
        return 1.5
    if ch == "09":
        return 3.0
    return 2.0


def filter_duplicate_01_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    01ch の重複除去
    除去条件①: 11-69ch に同一 (beat, sound_id) があれば 01ch を除去
    除去条件②: 01ch 同士で同一 (beat, sound_id) が重複すれば後発を除去
    Remove duplicate 01 channel events according to the rules in the original parser.

    Rules:
      * If a note on any playable channel (11-69) has the same beat and sound_id as an event,
        all subsequent 01 events with that beat/sound_id are removed.
      * Among 01 events themselves, later duplicates of the same beat/sound_id are removed.
    """
    playable_ch = _playable_channels()
    # Build a set of (beat, sound_id) pairs that already exist on playable channels
    existing_keys: set[tuple] = {
        (ev["beat"], ev.get("sound_id"))
        for ev in events
        if ev.get("channel") in playable_ch and ev.get("sound_id") is not None
    }

    seen_01: set[tuple] = set()
    filtered: list[dict[str, Any]] = []

    for ev in events:
        if ev.get("channel") == "01":
            key = (ev["beat"], ev.get("sound_id"))
            # Skip if the same note already exists on a playable channel
            if key in existing_keys or key in seen_01:
                continue
            seen_01.add(key)
        filtered.append(ev)

    return filtered


#def sort_events(events: list[dict[str, Any]]) -> None:
#    """Sort events by beat and priority."""
#    events.sort(key=lambda x: (x["beat"], get_event_priority(x)))


def calculate_event_times(events: list[dict[str, Any]], initial_bpm: float) -> None:
    """
    時系列順（beat順）にBPM変化とSTOPコマンドを適用しながら累積経過時間を計算する。
    Calculate absolute time for each event applying BPM/STOP changes.

    The function mutates `events` in place and assumes that the list is already sorted
    by beat.  It updates the 'time' key of every event.
    """
    current_sec = 0.0
    prev_beat = 0.0
    current_bpm = initial_bpm

    for ev in events:
        ev_beat = ev["beat"]
        delta_beat = ev_beat - prev_beat
        if delta_beat > 0:
            #逐次足しているので誤差が蓄積しうる処理
            current_sec += delta_beat * (60.0 / current_bpm)

        ev["time"] = current_sec

        # Apply BPM change
        if "bpm" in ev:
            current_bpm = ev["bpm"]

        # Apply STOP
        if "stop" in ev:
            #逐次足しているので誤差が蓄積しうる処理
            stop_sec = stop_seconds(ev["stop"], current_bpm)
            current_sec += stop_sec

        prev_beat = ev_beat


def resolve_ln_partners(events: list[dict[str, Any]]) -> None:
    """
    Link start and end long note events.

    The function mutates `events` in place.  For each LN channel it pairs a
    'start' event with the following 'end' event (if any) by adding reciprocal
    references (`ln_partner`, `ln_partner_beat`, `ln_partner_time`) to both.
    """
    ln_by_channel: dict[str, list[dict[str, Any]]] = {}

    for ev in events:
        if "ln_state" not in ev:
            continue

        ch = ev["channel"]
        # Normalise channel names so that 51/52/... and 61/62/... are treated the same
        if ch.startswith("5"):
            norm_ch = "1" + ch[1:]
        elif ch.startswith("6"):
            norm_ch = "2" + ch[1:]
        else:
            norm_ch = ch

        ln_by_channel.setdefault(norm_ch, []).append(ev)

    for evs in ln_by_channel.values():
        evs.sort(key=lambda x: x["beat"])
        start_ev = None
        for ev in evs:
            if ev.get("ln_state") == "start":
                start_ev = ev
            elif ev.get("ln_state") == "end" and start_ev is not None:
                # Link the two events
                start_ev["ln_partner_beat"] = ev["beat"]
                start_ev["ln_partner_time"] = ev["time"]
                start_ev["ln_partner"] = ev

                ev["ln_partner_beat"] = start_ev["beat"]
                ev["ln_partner_time"] = start_ev["time"]
                ev["ln_partner"] = start_ev
                start_ev = None


def build_timeline(info: dict[str, Any], events: list[dict[str, Any]], measures_multiplier: list[float]) -> BpmTimeline:
    """
    Construct a BpmTimeline instance from the event list.

    Parameters
    ----------
    info : dict
        Parsed chart information containing at least the 'bpm' key.
    events : list of dict
        The fully processed event list (sorted, with times calculated).
    measures_multiplier : list[float]
        Beat multipliers for each measure used to build the timeline.

    Returns
    -------
    BpmTimeline
        An instance representing BPM/STOP/SCROLL timelines.
    """
    bpm_timeline_events: list[tuple] = []
    stop_timeline_events: list[tuple] = []
    scroll_timeline_events: list[tuple] = []

    for ev in events:
        if "bpm" in ev:
            bpm_timeline_events.append((ev["beat"], ev["bpm"]))
        if "stop" in ev:
            stop_timeline_events.append((ev["beat"], ev["stop"]))
        if "scroll" in ev:
            scroll_timeline_events.append((ev["beat"], ev["scroll"]))

    return BpmTimeline(
        initial_bpm=info.get("bpm", 130.0),
        bpm_events=bpm_timeline_events,
        stop_events=stop_timeline_events,
        measures_multiplier=measures_multiplier,
        scroll_events=scroll_timeline_events,
    )
