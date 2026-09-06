import curses
from ui.base import BaseRenderer

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

        if self.mode == '14K':
            self.lane_count = 16
            self.half = 8
        elif self.mode == '10K':
            self.lane_count = 12
            self.half = 6
        elif self.mode == '9K':
            self.lane_count = 9
            self.half = 0
        elif self.mode in ('6K', '5K'):
            self.lane_count = 6
            self.half = 0
        elif self.mode == '4K':
            self.lane_count = 4
            self.half = 0
        else:  # 7K / default
            self.lane_count = 8
            self.half = 0

    def lane_posx(self, lane_idx: int) -> int:
        if self.half > 0 and lane_idx >= self.half:
            return self.lane_x + lane_idx + 1  # 1P/2P間の中央 '|' のため1文字右にシフト
        return self.lane_x + lane_idx

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
            self.safe_addstr(stdscr, self.judgement_y, self.lane_posx(i), char_str, attr)

        if self.half > 0:
            sep_x = self.lane_x + self.half
            self.safe_addstr(stdscr, self.judgement_y, sep_x, "|", base_gauge_attr)

        # Draw 1P/2P separator '|' for double play modes (10K/14K) background lines
        if self.half > 0:
            sep_x = self.lane_x + self.half
            for y in range(self.start_y, self.judgement_y):
                self.safe_addstr(stdscr, y, sep_x, "|", curses.A_DIM)

        # Draw measure lines (Background layer)
        if getattr(player, 'show_measure_lines', True):
            for i in range(event_index, len(events)):
                event = events[i]
                if event.get('state', 0) != 0 or event.get('channel') != 'measure_line':
                    continue

                y, _ = self.calculate_y(event, player, self.judgement_y, player_height, scale)
                if y < 0: break
                if self.start_y <= y < self.judgement_y:
                    if self.half > 0:
                        m_line = "-" * self.half + "|" + "-" * (self.lane_count - self.half)
                    else:
                        m_line = "-" * self.lane_count
                    self.safe_addstr(stdscr, y, self.lane_x, m_line, curses.A_DIM)

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

                x = self.lane_posx(lane_idx)

                # Head and tail rendering
                if start_ev.get('state', 0) == 0 and self.start_y <= y_start < self.judgement_y:
                    note_str = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                    head_char = note_str[0] if isinstance(note_str, str) and len(note_str) > 0 else "*"
                    self.safe_addstr(stdscr, y_start, x, head_char)
                if event.get('state', 0) == 0 and self.start_y <= y_end < self.judgement_y:
                    if settings.get('show_ln_end_head', False):
                        note_str = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                        end_char = note_str[0] if isinstance(note_str, str) and len(note_str) > 0 else "*"
                        self.safe_addstr(stdscr, y_end, x, end_char)
                    else:
                        self.safe_addstr(stdscr, y_end, x, "|")
                for y_body in range(max(self.start_y, y_end + 1), min(self.judgement_y, y_start)):
                    self.safe_addstr(stdscr, y_body, x, "|")

        # Draw notes (Foreground layer2)
        for i in range(event_index, len(events)):
            event = events[i]
            if event.get('state', 0) != 0:
                continue

            channel = event.get('channel')
            if channel == 'measure_line':
                continue

            # Skip LN end heads in standard note loop if show_ln_end_head is disabled
            if event.get('ln_state') == 'end' and not settings.get('show_ln_end_head', False):
                continue

            lane_idx = self.get_lane_index(channel, player)
            if lane_idx is None:
                continue

            y, _ = self.calculate_y(event, player, self.judgement_y, player_height, scale)
            if y < 0: break

            if event.get('is_mine'):
                note_str = "!"
                note_attr = curses.A_REVERSE
            else:
                # lane_chars values for Tiny should be 1-character string
                ch = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                note_str = ch[0] if isinstance(ch, str) and len(ch) > 0 else "*"
                note_attr = curses.A_NORMAL

            x_pos = self.lane_posx(lane_idx)

            if self.start_y <= y < self.judgement_y:
                self.safe_addstr(stdscr, y, x_pos, note_str, note_attr)

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
