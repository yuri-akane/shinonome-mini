import curses
import config
from ui.base import BaseRenderer

class MiniRenderer(BaseRenderer):
    """Mini (standard UI) Renderer."""

    def __init__(self, mode: str, judgement_y_config: int, lane_x: int = 4, start_y: int = 4):
        self.mode = mode.upper()
        self.is_dp = (self.mode in ('10K', '14K'))
        self.lane_x = lane_x
        self.start_y = start_y
        self.judgement_y = judgement_y_config

        if self.mode == '14K':
            self.lane_count = 16
            self.half = 8
            self.LANE_UNIT = "|" + "    |" * self.half + " " + "|" + "    |" * self.half
            self.JUDGE_UNIT = "+" + "----+" * self.half + " " + "+" + "----+" * self.half
        elif self.mode == '10K':
            self.lane_count = 12
            self.half = 6
            self.LANE_UNIT = "|" + "    |" * self.half + " " + "|" + "    |" * self.half
            self.JUDGE_UNIT = "+" + "----+" * self.half + " " + "+" + "----+" * self.half
        else:
            if self.mode == '9K':
                self.lane_count = 9
            elif self.mode in ('6K', '5K'):
                self.lane_count = 6
            elif self.mode == '4K':
                self.lane_count = 4
            else:  # 7K
                self.lane_count = 8
            self.half = 0
            self.LANE_UNIT = "|" + "    |" * self.lane_count
            self.JUDGE_UNIT = "+" + "----+" * self.lane_count

        if self.is_dp:
            self.stats_y = self.judgement_y + 5
            self.stat_x = self.lane_x + (self.lane_count // 2) * 5 + 2
        else:
            self.stats_y = self.start_y
            self.stat_x = self.lane_x + self.lane_count * 5 + 2

    def lane_posx(self, lane_idx: int) -> int:
        if self.mode in ('10K', '14K'):
            offset = 2 if lane_idx >= self.half else 0
            return self.lane_x + 1 + lane_idx * 5 + offset
        else:
            return self.lane_x + 1 + lane_idx * 5

    def render(self, stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play, settings, key_names, lane_chars, quit_key_code, key_to_lane, speedup_keycode, speeddown_keycode, use_pynput, get_key_events):
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

        self.safe_addstr(stdscr, 0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
        self.safe_addstr(stdscr, 1, 2, f"Song: {player.chart['info'].get('title', 'Unknown')} / Artist: {player.chart['info'].get('artist', 'Unknown')}")
        self.safe_addstr(stdscr, 2, 2, f"BPM: {current_bpm:.1f} | Time: {current_time:.2f}s | HS: {settings.get('hispeed', 1.0):.1f}")

        for y in range(self.start_y, self.judgement_y):
            self.safe_addstr(stdscr, y, self.lane_x, self.LANE_UNIT)

        self.safe_addstr(stdscr, self.judgement_y, self.lane_x, self.JUDGE_UNIT)

        for idx, name in enumerate(key_names):
            lane_idx = idx
            is_active = (current_time - player.key_pressed_time[lane_idx] < 0.12)
            attr = curses.A_REVERSE if is_active else curses.A_NORMAL
            self.safe_addstr(stdscr, self.judgement_y + 1, self.lane_posx(lane_idx), name, attr)

        if auto_play:
            self.safe_addstr(stdscr, self.judgement_y + 2, self.lane_x, "[       AUTOPLAY MODE ACTIVE       ]", curses.A_DIM)
        else:
            self.safe_addstr(stdscr, self.judgement_y + 2, self.lane_x, "[       MANUAL PLAY ACTIVE         ]")

        self.safe_addstr(stdscr, self.judgement_y + 4, self.lane_x, f"Press {config.quit_key_name} to quit playing")

        filled_segments = int(player.gauge / 5.0)
        bar_list = []
        for i in range(20):
            bar_list.append("=" if i < filled_segments else "-")
        bar_list.insert(16, "|")
        gauge_bar = "".join(bar_list)
        gauge_attr = curses.A_BOLD
        if player.hard_mode:
            gauge_mode_label = "HARD "
            gauge_mode_label2 = "SOLID" if settings['opt_solid'] else "GAUGE"
            if player.gauge <= 30.0:
                gauge_attr |= curses.A_BLINK
            elif player.gauge >= 80.0:
                gauge_attr |= curses.A_STANDOUT
        elif getattr(player, 'easy_mode', False):
            gauge_mode_label = "EASY "
            gauge_mode_label2 = "SOLID" if settings['opt_solid'] else "GAUGE"
            if player.gauge >= 80.0:
                gauge_attr |= curses.A_STANDOUT
        else:
            gauge_mode_label = ""
            gauge_mode_label2 = "SOLID GAUGE" if settings['opt_solid'] else "GAUGE"
            if player.gauge >= 80.0:
                gauge_attr |= curses.A_STANDOUT
        self.safe_addstr(stdscr, self.stats_y, self.stat_x, f"{gauge_mode_label}{gauge_mode_label2}: [{gauge_bar}] {player.gauge:5.1f}%", gauge_attr)

        max_score = player.total_playable_notes * 2
        self.safe_addstr(stdscr, self.stats_y + 2, self.stat_x, f"EX SCORE: {player.ex_score:5d} / {max_score:5d}")

        combo_attr = curses.A_NORMAL
        if player.combo > 0 and player.combo == player.max_combo:
            combo_attr = curses.A_BOLD
        self.safe_addstr(stdscr, self.stats_y + 3, self.stat_x, f"COMBO   : {player.combo:5d}  (MAX: {player.max_combo:5d})", combo_attr)

        self.safe_addstr(stdscr, self.stats_y + 5, self.stat_x, f"P: {player.perfect_count:3d} G: {player.great_count:3d} g: {player.good_count:3d} B: {player.bad_count:3d} M: {player.miss_count:3d}", curses.A_UNDERLINE)

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
            elif player.last_judgement == "MINE":
                attr |= curses.A_REVERSE | curses.A_BLINK
            self.safe_addstr(stdscr, self.judgement_y + 6, self.lane_x + 12, j_str, attr)
            if player.combo >= 3 and player.last_judgement in ["PERFECT", "GREAT", "GOOD"]:
                self.safe_addstr(stdscr, self.judgement_y + 7, self.lane_x + 14, f"{player.combo} COMBO", curses.A_BOLD)

        # Draw measure lines (Background layer)
        if getattr(player, 'show_measure_lines', True):
            for i in range(event_index, len(events)):
                event = events[i]
                if event.get('state', 0) != 0 or event.get('channel') != 'measure_line':
                    continue

                y, _ = self.calculate_y(event, player, self.judgement_y, player_height, scale)
                if y < 0: break
                if self.start_y <= y < self.judgement_y:
                    self.safe_addstr(stdscr, y, self.lane_x, self.JUDGE_UNIT, curses.A_DIM)

        # Draw long note bodies (Foreground layer1)
        for i in range(event_index, len(events)):
            event = events[i]
            if event.get('state', 0) != 0:
                continue

            channel = event.get('channel')
            lane_idx = self.get_lane_index(channel, player) if channel else None
            if lane_idx is None:
                continue

            if event.get('ln_state') == 'end':
                start_ev = event.get('ln_partner')
                if not start_ev:
                    continue

                y_end, _ = self.calculate_y(event, player, self.judgement_y, player_height, scale)

                if start_ev.get('state', 0) == 1:
                    y_start = self.judgement_y
                else:
                    y_start, _ = self.calculate_y(start_ev, player, self.judgement_y, player_height, scale)
                    
                note_str = lane_chars[lane_idx]
                x = self.lane_posx(lane_idx)

                if start_ev.get('state', 0) == 0 and self.start_y <= y_start < self.judgement_y:
                    self.safe_addstr(stdscr, y_start, x, note_str)
                if event.get('state', 0) == 0 and self.start_y <= y_end < self.judgement_y:
                    if settings.get('show_ln_end_head', False):
                        self.safe_addstr(stdscr, y_end, x, note_str)
                    else:
                        self.safe_addstr(stdscr, y_end, x, " |")
                for y_body in range(max(self.start_y, y_end + 1), min(self.judgement_y, y_start)):
                    self.safe_addstr(stdscr, y_body, x, " |")

        # Draw notes (Foreground layer2)
        for i in range(event_index, len(events)):
            event = events[i]
            if event.get('state', 0) != 0:
                continue

            channel = event.get('channel')
            if channel == 'measure_line':
                continue

            if event.get('ln_state') == 'end' and not settings.get('show_ln_end_head', False):
                continue

            lane_idx = self.get_lane_index(channel, player)
            if lane_idx is None:
                continue

            y, target_seconds = self.calculate_y(event, player, self.judgement_y, player_height, scale)
            if y < 0: break

            note_str = "M!" if event.get('is_mine') else lane_chars[lane_idx]
            note_attr = curses.A_REVERSE if event.get('is_mine') else curses.A_NORMAL
            x_pos = self.lane_posx(lane_idx)

            if self.start_y <= y < self.judgement_y:
                self.safe_addstr(stdscr, y, x_pos, note_str, note_attr)
            elif y >= self.judgement_y:
                if current_time - target_seconds < 0.08:
                    self.safe_addstr(stdscr, self.judgement_y, x_pos, "FL", curses.A_REVERSE)

        beat_seconds = 60.0 / initial_bpm
        beat_number = int(current_time / beat_seconds)
        if beat_number % 2 == 0:
            self.safe_addstr(stdscr, self.judgement_y, self.lane_x - 2, "*", curses.A_BOLD)
        else:
            self.safe_addstr(stdscr, self.judgement_y, self.lane_x - 2, " ")
        rotation_symbols = ["|", "/", "-", "\\"]
        half_beat_number = int(current_time / (beat_seconds * 0.5))
        rot_char = rotation_symbols[half_beat_number % 4]
        self.safe_addstr(stdscr, self.judgement_y + 1, self.lane_x - 2, rot_char, curses.A_BOLD)

        # Handle input
        while True:
            ch = stdscr.getch()
            if ch == -1:
                break
            if ch == quit_key_code:
                player.is_playing = False
                continue
            if ch in key_to_lane:
                if not auto_play:
                    player.press_key(key_to_lane[ch])
                continue
            if ch == speedup_keycode:
                settings['hispeed'] = min(settings.get('hispeed', 1.0) + 0.2, 100.0)
            elif ch == speeddown_keycode:
                settings['hispeed'] = max(settings.get('hispeed', 1.0) - 0.2, 0.2)

        key_events = get_key_events() if (use_pynput and get_key_events) else []
        for ev_type, k in key_events:
            if ev_type != "press" or not k:
                continue
            if k.startswith("'") and k.endswith("'") and len(k) >= 3:
                k = k[1:-1]
            if k.startswith("Key."):
                k = k[4:]
            mod_keys = settings.get('modifier_keys', {})
            if k in mod_keys:
                if not auto_play:
                    player.press_key(mod_keys[k])
                continue
