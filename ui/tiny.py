import curses
from ui.base import BaseRenderer, lane_info

class TinyRenderer(BaseRenderer):
    """Tiny (ultra-compact UI) Renderer.
    
    Fits in ~10x8 area.
    - 1 char note width per lane with no space gap between lanes.
    - Judgement line serves as the gauge display bar.
    - Mine: '!' (curses.A_REVERSE)
    - Long Note (head, body, end): '|'
    - No FL flash, no stats panel, no key names.
    """

    def __init__(self, mode: str, judgement_y_config: int = 7, lane_x: int = 1, start_y: int = 0):
        self.mode = mode.upper()
        self.is_dp = (self.mode in ('10K', '14K'))
        self.lane_x = lane_x
        self.start_y = start_y
        self.judgement_y = judgement_y_config

        self.lane_count, self.half = lane_info(self.mode)

    def lane_posx(self, lane_idx: int) -> int:
        if self.half > 0 and lane_idx >= self.half:
            return self.lane_x + lane_idx + 1  # 1P/2P間の中央 '|' のため1文字右にシフト
        return self.lane_x + lane_idx

    def render(self, stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play, opts, key_names, lane_chars, key_to_lane, use_pynput, get_key_events):
        draw_time = self.get_draw_time(current_time, opts)
        scale, player_height, current_bpm = self.calculate_scale_and_state(player, draw_time, initial_bpm, opts)

        is_reverse_bpm = (current_bpm < 0)

        if is_reverse_bpm:
            judge_y = self.start_y
            lane_top = self.start_y + 1
            lane_bottom = self.judgement_y + 1
        else:
            judge_y = self.judgement_y
            lane_top = self.start_y
            lane_bottom = self.judgement_y

        # Render Judgement Line as Gauge Bar
        # Gauge range 0.0 ~ 100.0 mapped across lane_count chars
        filled_cnt = int(round((player.gauge / 100.0) * self.lane_count))
        base_gauge_attr = curses.A_BOLD
        if player.hard_mode and player.gauge <= 30.0:
            base_gauge_attr |= curses.A_BLINK
        elif player.gauge >= 80.0:
            base_gauge_attr |= curses.A_REVERSE

        # Draw gauge bar character by character so active lane keypress toggles reverse state
        for i in range(self.lane_count):
            char_str = "=" if i < filled_cnt else "-"
            attr = base_gauge_attr
            if i < len(player.key_pressed_time) and (current_time - player.key_pressed_time[i] < 0.12):
                attr ^= curses.A_REVERSE
            self.safe_addstr(stdscr, judge_y, self.lane_posx(i), char_str, attr)

        if self.half > 0:
            sep_x = self.lane_x + self.half
            self.safe_addstr(stdscr, judge_y, sep_x, "|", base_gauge_attr)

        # Draw 1P/2P separator '|' for double play modes (10K/14K) background lines
        if self.half > 0:
            sep_x = self.lane_x + self.half
            for y in range(lane_top, lane_bottom):
                self.safe_addstr(stdscr, y, sep_x, "|", curses.A_DIM)

        draw_start_idx = self.get_draw_start_index(events, draw_time)

        def calc_event_y(ev):
            if is_reverse_bpm:
                target_seconds = ev['time']
                if getattr(player, 'timeline', None):
                    note_height = player.timeline.get_height_at_beat(ev['beat'])
                else:
                    note_height = target_seconds
                y_calc = judge_y + int((note_height - player_height) * abs(scale))
                return y_calc, target_seconds
            else:
                return self.calculate_y(ev, player, judge_y, player_height, scale)

        # Draw measure lines (Background layer)
        if getattr(player, 'show_measure_lines', True):
            for i in range(draw_start_idx, len(events)):
                event = events[i]
                if event.get('channel') != 'measure_line':
                    continue

                y, _ = calc_event_y(event)
                if not is_reverse_bpm and scale >= 0 and y < 0:
                    break
                if (is_reverse_bpm or scale < 0) and y > curses.LINES:
                    break
                if lane_top <= y < lane_bottom:
                    if self.half > 0:
                        m_line = "-" * self.half + "|" + "-" * (self.lane_count - self.half)
                    else:
                        m_line = "-" * self.lane_count
                    self.safe_addstr(stdscr, y, self.lane_x, m_line, curses.A_DIM)

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

            y_end, _ = calc_event_y(event)

            if start_ev.get('manual_hit') or (draw_time >= start_ev.get('time', 0.0)):
                y_start = judge_y
            else:
                y_start, _ = calc_event_y(start_ev)

            x = self.lane_posx(lane_idx)

            # Head and tail rendering
            if not start_ev.get('manual_hit') and draw_time < start_ev.get('time', 0.0) and lane_top <= y_start < lane_bottom:
                note_str = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                head_char = note_str[0] if isinstance(note_str, str) and len(note_str) > 0 else "*"
                self.safe_addstr(stdscr, y_start, x, head_char)
            if lane_top <= y_end < lane_bottom:
                if opts.show_ln_end_head:
                    note_str = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                    end_char = note_str[0] if isinstance(note_str, str) and len(note_str) > 0 else "*"
                    self.safe_addstr(stdscr, y_end, x, end_char)
                else:
                    self.safe_addstr(stdscr, y_end, x, "|")

            body_top = min(y_start, y_end)
            body_bottom = max(y_start, y_end)
            draw_top = max(lane_top, body_top + 1)
            draw_bottom = min(lane_bottom, body_bottom)
            for y_body in range(draw_top, draw_bottom):
                self.safe_addstr(stdscr, y_body, x, "|")

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

            y, _ = calc_event_y(event)
            if not is_reverse_bpm and scale >= 0 and y < 0:
                break
            if (is_reverse_bpm or scale < 0) and y > curses.LINES:
                break

            if event.get('is_mine'):
                note_str = "!"
                note_attr = curses.A_REVERSE
            else:
                # lane_chars values for Tiny should be 1-character string
                ch = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                note_str = ch[0] if isinstance(ch, str) and len(ch) > 0 else "*"
                note_attr = curses.A_NORMAL

            x_pos = self.lane_posx(lane_idx)

            if lane_top <= y < lane_bottom:
                self.safe_addstr(stdscr, y, x_pos, note_str, note_attr)

        self.process_input(stdscr, player, auto_play, opts, key_to_lane, use_pynput, get_key_events)
