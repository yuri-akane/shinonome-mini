import curses
from ui.base import BaseRenderer, lane_info

class MiniRenderer(BaseRenderer):
    """Mini (standard UI) Renderer."""

    def __init__(self, mode: str, judgement_y_config: int, lane_x: int = 4, start_y: int = 4):
        self.mode = mode.upper()
        self.is_dp = (self.mode in ('10K', '14K'))
        self.lane_x = lane_x
        self.start_y = start_y
        self.judgement_y = judgement_y_config

        self.lane_count, self.half = lane_info(self.mode)
        if self.half > 0:
            self.LANE_UNIT = "|" + "    |" * self.half + " " + "|" + "    |" * self.half
            self.JUDGE_UNIT = "+" + "----+" * self.half + " " + "+" + "----+" * self.half
        else:
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

    def render(self, stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play, opts, key_names, lane_chars, key_to_lane, use_pynput, get_key_events):
        draw_time = self.get_draw_time(current_time, opts)
        scale, player_height, current_bpm = self.calculate_scale_and_state(player, draw_time, initial_bpm, opts)

        self.safe_addstr(stdscr, 0, 2, "Shinonome-Mini -- Minimal Console BMS Player", curses.A_BOLD)
        self.safe_addstr(stdscr, 1, 2, f"Song: {player.chart['info'].get('title', '___')} / Artist: {player.chart['info'].get('artist', '___')}")
        self.safe_addstr(stdscr, 2, 2, f"BPM: {current_bpm:.1f} | Time: {draw_time:.2f}s | HS: {opts.hispeed:.1f}")

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

        #quit_key_name = opts.quit_key_name
        self.safe_addstr(stdscr, self.judgement_y + 4, self.lane_x, f"Press {opts.quit_key_name} to quit playing")

        filled_segments = int(player.gauge / 5.0)
        bar_list = []
        for i in range(20):
            bar_list.append("=" if i < filled_segments else "-")
        bar_list.insert(16, "|")
        gauge_bar = "".join(bar_list)
        gauge_attr = curses.A_BOLD
        if player.hard_mode:
            gauge_mode_label = "HARD "
            gauge_mode_label2 = "SOLID" if opts.solid else "GAUGE"
            if player.gauge <= 30.0:
                gauge_attr |= curses.A_BLINK
            elif player.gauge >= 80.0:
                gauge_attr |= curses.A_STANDOUT
        elif getattr(player, 'easy_mode', False):
            gauge_mode_label = "EASY "
            gauge_mode_label2 = "SOLID" if opts.solid else "GAUGE"
            if player.gauge >= 80.0:
                gauge_attr |= curses.A_STANDOUT
        else:
            gauge_mode_label = ""
            gauge_mode_label2 = "SOLID GAUGE" if opts.solid else "GAUGE"
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

        draw_start_idx = self.get_draw_start_index(events, draw_time)

        # Draw measure lines (Background layer)
        if getattr(player, 'show_measure_lines', True):
            for i in range(draw_start_idx, len(events)):
                event = events[i]
                if event.get('channel') != 'measure_line':
                    continue

                y, _ = self.calculate_y(event, player, self.judgement_y, player_height, scale)
                if y < 0: break
                if self.start_y <= y < self.judgement_y:
                    self.safe_addstr(stdscr, y, self.lane_x, self.JUDGE_UNIT, curses.A_DIM)

        # Draw long note bodies (Foreground layer1)
        for i in range(draw_start_idx, len(events)):
            event = events[i]
            if event.get('ln_state') != 'end':
                continue
            if not self.is_note_visible(event, draw_time):
                continue

            channel = event.get('channel')
            lane_idx = self.get_lane_index(channel, player) if channel else None
            if lane_idx is None:
                continue

            start_ev = event.get('ln_partner')
            if not start_ev:
                continue

            y_end, _ = self.calculate_y(event, player, self.judgement_y, player_height, scale)

            if start_ev.get('manual_hit') or (draw_time >= start_ev.get('time', 0.0)):
                y_start = self.judgement_y
            else:
                y_start, _ = self.calculate_y(start_ev, player, self.judgement_y, player_height, scale)
                
            note_str = lane_chars[lane_idx]
            x = self.lane_posx(lane_idx)

            if not start_ev.get('manual_hit') and draw_time < start_ev.get('time', 0.0) and self.start_y <= y_start < self.judgement_y:
                self.safe_addstr(stdscr, y_start, x, note_str)
            if self.start_y <= y_end < self.judgement_y:
                if opts.show_ln_end_head:
                    self.safe_addstr(stdscr, y_end, x, note_str)
                else:
                    self.safe_addstr(stdscr, y_end, x, " |")
            for y_body in range(max(self.start_y, y_end + 1), min(self.judgement_y, y_start)):
                self.safe_addstr(stdscr, y_body, x, " |")

        # Draw notes (Foreground layer2)
        for i in range(draw_start_idx, len(events)):
            event = events[i]
            channel = event.get('channel')
            if channel == 'measure_line':
                continue

            # Skip LN end heads in standard note loop if show_ln_end_head is disabled
            if event.get('ln_state') == 'end' and not opts.show_ln_end_head:
                continue

            if not self.is_note_visible(event, draw_time):
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
                if draw_time - target_seconds < 0.08:
                    self.safe_addstr(stdscr, self.judgement_y, x_pos, "FL", curses.A_REVERSE)

        beat_seconds = 60.0 / initial_bpm
        beat_number = int(draw_time / beat_seconds)
        if beat_number % 2 == 0:
            self.safe_addstr(stdscr, self.judgement_y, self.lane_x - 2, "*", curses.A_BOLD)
        else:
            self.safe_addstr(stdscr, self.judgement_y, self.lane_x - 2, " ")
        rotation_symbols = ["|", "/", "-", "\\"]
        half_beat_number = int(draw_time / (beat_seconds * 0.5))
        rot_char = rotation_symbols[half_beat_number % 4]
        self.safe_addstr(stdscr, self.judgement_y + 1, self.lane_x - 2, rot_char, curses.A_BOLD)

        self.process_input(stdscr, player, auto_play, opts, key_to_lane, use_pynput, get_key_events)
