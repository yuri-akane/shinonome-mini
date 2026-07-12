import curses
import config
from key_listener import start_key_listener, get_key_events
from constants import (
    CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT,
    LANE_CHARS_LEFT, LANE_CHARS_RIGHT,
    KEY_NAMES_DP, KEY_NAMES_RIGHT, KEY_NAMES_LEFT,
)

def make_on_update(stdscr, player, quit_key_code, key_to_lane, judgement_y_config, settings, lane_chars):
    """Create an update callback for the player.

    Parameters:
        stdscr: curses window
        player: Player instance
        quit_key_code: key code to quit
        key_to_lane: mapping of input keys to lanes
        judgement_y_config: y-position for judgement line
        settings: mutable settings dict (e.g., hispeed)
        lane_chars: list of characters representing notes per lane
    """
    def on_update(current_time, events, event_index, initial_bpm, resolution, auto_play):
        # Ensure key listener is running (only start once)
        if not getattr(on_update, "_listener_started", False):
            start_key_listener()
            on_update._listener_started = True
        try:
            stdscr.erase()

            # 画面サイズの確認 (DP時に統計情報を下げたため、必要なYサイズを拡張)
            max_y, max_x = stdscr.getmaxyx()
            is_dp = (player.chart.get('mode', 'SP') == 'DP')
            required_y = 32 if is_dp else 22
            required_x = 100 if is_dp else 70
            if max_y < required_y or max_x < required_x:
                stdscr.addstr(0, 2, "=== TERMINAL SIZE TOO SMALL ===", curses.A_BOLD)
                stdscr.addstr(2, 2, f"Required size: {required_x} cols x {required_y} rows")
                stdscr.addstr(3, 2, f"Current size : {max_x} cols x {max_y} rows")

            judgement_y = judgement_y_config
            start_y = 4
            lane_x = 4
            base_speed = 22.0
            speed = base_speed * settings.get('hispeed', 1.0)

            if getattr(player, 'timeline', None):
                beat_duration = 60.0 / player.initial_bpm
                scale = speed * beat_duration
                _, player_height, current_bpm, _ = player.timeline.get_state(current_time)
            else:
                scale = speed
                player_height = current_time
                current_bpm = getattr(player, 'current_bpm', initial_bpm)

            stdscr.addstr(0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
            stdscr.addstr(1, 2, f"Song: {player.chart['info'].get('title', 'Unknown')} / Artist: {player.chart['info'].get('artist', 'Unknown')}")
            stdscr.addstr(2, 2, f"BPM: {current_bpm:.1f} | Time: {current_time:.2f}s | HS: {settings.get('hispeed', 1.0):.1f}")
            #stdscr.addstr(3, 2, f"HS: {settings.get('hispeed', 1.0):.1f}")

            lane_count = 16 if player.chart.get('mode', 'SP') == 'DP' else 8
            for y in range(start_y, judgement_y):
                if lane_count == 16:
                    stdscr.addstr(y, lane_x, "|" + "    |" * 8 + " " + "|" + "    |" * 8)
                else:
                    stdscr.addstr(y, lane_x, "|" + "    |" * lane_count)
            if lane_count == 16:
                stdscr.addstr(judgement_y, lane_x, "+" + "----+" * 8 + " " + "+" + "----+" * 8)
            else:
                stdscr.addstr(judgement_y, lane_x, "+" + "----+" * lane_count)

            if player.chart.get('mode', 'SP') == 'DP':
                key_names = KEY_NAMES_DP
            elif settings['opt_scratch_side'] == "right":
                key_names = KEY_NAMES_RIGHT
            else:
                key_names = KEY_NAMES_LEFT

            for idx, name in enumerate(key_names):
                lane_idx = idx
                is_active = (current_time - player.key_pressed_time[lane_idx] < 0.12)
                attr = curses.A_REVERSE if is_active else curses.A_NORMAL
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

            if player.chart.get('mode', 'SP') == 'DP':
                stats_y = judgement_y + 5
                stat_x = lane_x + (lane_count // 2) * 5 + 2
            else:
                stats_y = start_y
                stat_x = lane_x + lane_count * 5 + 2

            filled_segments = int(player.gauge / 5.0)
            bar_list = []
            for i in range(20):
                bar_list.append("=" if i < filled_segments else "-")
            bar_list.insert(16, "|")
            gauge_bar = "".join(bar_list)
            gauge_attr = curses.A_BOLD
            if player.hard_mode:
                gauge_mode_label = "HARD "
                if player.gauge <= 30.0:
                    gauge_attr |= curses.A_BLINK   # 低ゲージ警告
                elif player.gauge >= 80.0:
                    gauge_attr |= curses.A_STANDOUT
            elif getattr(player, 'easy_mode', False):
                gauge_mode_label = "EASY "
                if player.gauge >= 80.0:
                    gauge_attr |= curses.A_STANDOUT
            else:
                gauge_mode_label = ""
                if player.gauge >= 80.0:
                    gauge_attr |= curses.A_STANDOUT
            stdscr.addstr(stats_y, stat_x, f"{gauge_mode_label}GAUGE: [{gauge_bar}] {player.gauge:5.1f}%", gauge_attr)

            max_score = player.total_playable_notes * 2
            stdscr.addstr(stats_y + 2, stat_x, f"EX SCORE: {player.ex_score:5d} / {max_score:5d}")

            combo_attr = curses.A_NORMAL
            if player.combo > 0 and player.combo == player.max_combo:
                combo_attr = curses.A_BOLD
            stdscr.addstr(stats_y + 3, stat_x, f"COMBO   : {player.combo:5d}  (MAX: {player.max_combo:5d})", combo_attr)

            stdscr.addstr(stats_y + 5, stat_x, f"P: {player.perfect_count:3d} G: {player.great_count:3d} g: {player.good_count:3d} B: {player.bad_count:3d} M: {player.miss_count:3d}", curses.A_UNDERLINE)

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
                if player.combo >= 3 and player.last_judgement in ["PERFECT", "GREAT", "GOOD"]:
                    stdscr.addstr(judgement_y + 7, lane_x + 14, f"{player.combo} COMBO", curses.A_BOLD)

            # Draw long note bodies first
            for i in range(event_index, len(events)):
                event = events[i]
                if event.get('state', 0) != 0:
                    continue
                channel = event.get('channel')
                if not channel:
                    continue
                # Support standard channels and extended 51-69 channels
                if channel in player.channel_to_lane:
                    lane_idx = player.channel_to_lane[channel]
                elif channel.isdigit() and 51 <= int(channel) <= 69:
                    # Map extended channels to their base lane by subtracting 40 (e.g., 51 -> 11)
                    base_chan = str(int(channel) - 40)
                    lane_idx = player.channel_to_lane.get(base_chan)
                    if lane_idx is None:
                        continue
                else:
                    continue
                if event.get('ln_state') == 'end':
                    start_ev = event.get('ln_partner')
                    if start_ev:
                        # Use previously resolved lane_idx for end events
                        # lane_idx already set correctly for standard and extended channels
                        # No need to re‑lookup in player.channel_to_lane
                        # (previous code caused KeyError for 51‑69 channels)
                        if lane_count == 16 and lane_idx >= 8:
                            x = lane_x + 1 + lane_idx * 5 + 2
                        else:
                            x = lane_x + 1 + lane_idx * 5
                        
                        target_seconds_end = event['time']
                        if getattr(player, 'timeline', None):
                            note_height_end = player.timeline.get_height_at_beat(event['beat'])
                        else:
                            note_height_end = target_seconds_end
                        y_end = judgement_y - int((note_height_end - player_height) * scale)
                        
                        if start_ev.get('state', 0) == 1:
                            y_start = judgement_y
                        else:
                            target_seconds_start = start_ev['time']
                            if getattr(player, 'timeline', None):
                                note_height_start = player.timeline.get_height_at_beat(start_ev['beat'])
                            else:
                                note_height_start = target_seconds_start
                            y_start = judgement_y - int((note_height_start - player_height) * scale)
                        
                        # Draw start head (if not already hit) and end head for LNTYPE1
                        note_str = lane_chars[lane_idx]
                        # start head (visible when pending)
                        if start_ev.get('state', 0) == 0 and start_y <= y_start < judgement_y:
                            stdscr.addstr(y_start, x, note_str)
                        # end head (visible when pending)
                        if event.get('state', 0) == 0 and start_y <= y_end < judgement_y:
                            stdscr.addstr(y_end, x, note_str)
                        # draw long body
                        for y_body in range(max(start_y, y_end + 1), min(judgement_y, y_start)):
                            stdscr.addstr(y_body, x, " |")

            for i in range(event_index, len(events)):
                event = events[i]
                if event.get('state', 0) != 0:
                    continue
                channel = event.get('channel')
                is_measure_line = (channel == 'measure_line')
                if is_measure_line and not getattr(player, 'show_measure_lines', True):
                    continue
                if not is_measure_line:
                    # Support standard and extended channels for rendering start notes
                    if channel in player.channel_to_lane:
                        lane_idx = player.channel_to_lane[channel]
                    elif channel.isdigit() and 51 <= int(channel) <= 69:
                        base_chan = str(int(channel) - 40)
                        lane_idx = player.channel_to_lane.get(base_chan)
                        if lane_idx is None:
                            continue
                    else:
                        continue
                    note_str = lane_chars[lane_idx]
                target_seconds = event['time']
                if getattr(player, 'timeline', None):
                    note_height = player.timeline.get_height_at_beat(event['beat'])
                else:
                    note_height = target_seconds
                y = judgement_y - int((note_height - player_height) * scale)
                if start_y <= y < judgement_y:
                    if is_measure_line:
                        if lane_count == 16:
                            line_str = "+" + "----+" * 8 + " " + "+" + "----+" * 8
                        else:
                            line_str = "+" + "----+" * lane_count
                        stdscr.addstr(y, lane_x, line_str, curses.A_DIM)
                    else:
                        if lane_count == 16 and lane_idx >= 8:
                            x = lane_x + 1 + lane_idx * 5 + 2
                        else:
                            x = lane_x + 1 + lane_idx * 5
                        stdscr.addstr(y, x, note_str)
                elif y >= judgement_y and not is_measure_line:
                    if current_time - target_seconds < 0.08:
                        if lane_count == 16 and lane_idx >= 8:
                            x = lane_x + 1 + lane_idx * 5 + 2
                        else:
                            x = lane_x + 1 + lane_idx * 5
                        stdscr.addstr(judgement_y, x, "FL", curses.A_REVERSE)
                if y < 0:
                    break

            beat_seconds = 60.0 / initial_bpm
            beat_number = int(current_time / beat_seconds)
            if beat_number % 2 == 0:
                stdscr.addstr(judgement_y, lane_x - 2, "*", curses.A_BOLD)
            else:
                stdscr.addstr(judgement_y, lane_x - 2, " ")
            rotation_symbols = ["|", "/", "-", "\\"]
            half_beat_number = int(current_time / (beat_seconds * 0.5))
            rot_char = rotation_symbols[half_beat_number % 4]
            stdscr.addstr(judgement_y + 1, lane_x - 2, rot_char, curses.A_BOLD)

            # Process curses keyboard input (normal keys + esc)
            while True:
                ch = stdscr.getch()
                if ch == -1:
                    break
                # Quit key
                if ch == quit_key_code:
                    player.is_playing = False
                    continue
                # Lane key handling
                if ch in key_to_lane:
                    if not auto_play:
                        player.press_key(key_to_lane[ch])
                    continue
                # Hispeed adjustments (configurable keys)
                speedup_key = settings.get('speedup_key', '+')
                speeddown_key = settings.get('speeddown_key', '-')
                def _key_code(k):
                    # Convert a key identifier to curses key code
                    if isinstance(k, str):
                        uk = k.upper()
                        if uk == 'KEY_UP':
                            return curses.KEY_UP
                        if uk == 'KEY_DOWN':
                            return curses.KEY_DOWN
                        # Fallback: single character
                        return ord(k)
                    return k
                if ch == _key_code(speedup_key):
                    settings['hispeed'] = min(settings.get('hispeed', 1.0) + 0.2, 100.0)
                elif ch == _key_code(speeddown_key):
                    settings['hispeed'] = max(settings.get('hispeed', 1.0) - 0.2, 0.2)

            # Process keyboard input using pynput for modifier keys
            key_events = get_key_events()
            for ev_type, k in key_events:
                if ev_type != "press":
                    continue
                if not k:
                    continue
                # Clean up quotes if present (e.g. "'z'" -> "z")
                if k.startswith("'") and k.endswith("'") and len(k) >= 3:
                    k = k[1:-1]
                
                # Strip "Key." prefix if present (e.g. "Key.esc" -> "esc")
                if k.startswith("Key."):
                    k = k[4:]

                # Modifier keys: stop playback using configurable mapping
                mod_keys = settings.get('modifier_keys', {})
                if k in mod_keys:
                    if not auto_play:
                        player.press_key(mod_keys[k])
                    continue
            stdscr.refresh()
        except curses.error:
            pass
    return on_update
