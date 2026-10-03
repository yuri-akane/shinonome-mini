import curses
from ui.base import BaseRenderer, lane_info

class MwRenderer(BaseRenderer):
    """MixWaver Mode (Horizontal 2-Pane Alternating Scanning) Renderer.
    ui/mw.py - MixWaver Mode (Horizontal Play Mode) Renderer with 2-Pane Alternating Scanning

    MixWaver (MW) mode renders two horizontal panes (Upper Pane & Lower Pane).
    The scanning judgement line sweeps across Upper Pane (Measure N), then moves to
    Lower Pane (Measure N+1), wrapping back to Upper Pane (Measure N+2) seamlessly.
    """

    def __init__(self, mode: str, judgement_y_config: int = 12, lane_x: int = 8, start_y: int = 3):
        self.mode = mode.upper()
        self.is_dp = (self.mode in ('10K', '14K'))
        self.lane_x = lane_x
        self.start_y = start_y
        self.judgement_y = judgement_y_config

        self.lane_count, self.half = lane_info(self.mode)
        self.last_judge_x = self.lane_x
        if self.mode == '14K':
            self.lane_labels = [
                "1SC", "1K1", "1K2", "1K3", "1K4", "1K5", "1K6", "1K7",
                "2K1", "2K2", "2K3", "2K4", "2K5", "2K6", "2K7", "2SC"
            ]
        elif self.mode == '10K':
            self.lane_labels = [
                "1SC", "1K1", "1K2", "1K3", "1K4", "1K5",
                "2K1", "2K2", "2K3", "2K4", "2K5", "2SC"
            ]
        elif self.mode == '9K':
            self.lane_labels = ["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9"]
        elif self.mode in ('5K'):
            self.lane_labels = ["SC", "K1", "K2", "K3", "K4", "K5"] #todo: あとで右スクラッチも
        elif self.mode in ('6K'):
            self.lane_labels = ["K1", "K2", "K3", "K4", "K5", "K6"]
        elif self.mode == '4K':
            self.lane_labels = ["K1", "K2", "K3", "K4"]
        else:  # 7K / default
            self.lane_labels = ["SC", "K1", "K2", "K3", "K4", "K5", "K6", "K7"] #todo: あとで右スクラッチも

    def _render_pane(self, stdscr, pane_title: str, start_y: int, start_beat: float, beats_per_window: float,
                     beat_width: float, track_width: int, is_active: bool, current_beat: float, current_time: float,
                     events: list, event_index: int, player, lane_chars, opts, max_y: int, max_x: int,
                     use_fixed_judge: bool = False):

        end_beat = start_beat + beats_per_window
        dp_offset = 1 if (self.is_dp and self.half > 0) else 0

        # Draw Pane Title Header & Top Border (横幅100%)
        border_title = f"[ {pane_title} ]"
        full_width = max(10, max_x - 1)
        border_dashes = max(0, full_width - len(border_title) - 4)
        border_str = f"+--{border_title}" + "-" * border_dashes + "+"
        top_attr = curses.A_BOLD if is_active else curses.A_DIM
        self.safe_addstr(stdscr, start_y, 0, border_str, top_attr)

        # 背景は空欄（スペース）で初期化し、リガチャ/字詰めによるセル幅ズレを防ぐ
        track_line = " " * track_width

        # Draw Lanes, Labels, and Track Background
        for idx in range(self.lane_count):
            offset = 1 if (self.is_dp and self.half > 0 and idx >= self.half) else 0
            row_y = start_y + 1 + idx + offset
            if row_y >= max_y - 2:
                break

            label = self.lane_labels[idx] if idx < len(self.lane_labels) else f"L{idx}"
            is_key_active = (idx < len(player.key_pressed_time)) and (current_time - player.key_pressed_time[idx] < 0.12)
            label_attr = curses.A_REVERSE if is_key_active else (curses.A_BOLD if is_active else curses.A_NORMAL)
            self.safe_addstr(stdscr, row_y, 1, f"[{label:^3s}]", label_attr)

            self.safe_addstr(stdscr, row_y, self.lane_x, track_line, curses.A_NORMAL)

        # Draw DP Middle Separator (1Pと2Pの間の中間線)
        if self.is_dp and self.half > 0:
            mid_y = start_y + 1 + self.half
            if mid_y < max_y - 2:
                self.safe_addstr(stdscr, mid_y, 1, "[---]", curses.A_DIM)
                self.safe_addstr(stdscr, mid_y, self.lane_x, "-" * track_width, curses.A_DIM)

        bottom_y = start_y + 1 + self.lane_count + dp_offset
        bot_border = "+" + "-" * max(0, full_width - 2) + "+"
        if bottom_y < max_y - 1:
            self.safe_addstr(stdscr, bottom_y, 0, bot_border, curses.A_DIM)

        # 判定ラインX座標の決定（高速ギミック時は保持した位置、通常時は進行beatに応じた位置）
        if use_fixed_judge:
            judge_x = self.last_judge_x
        else:
            judge_rel_beat = max(0.0, min(beats_per_window, current_beat - start_beat))
            judge_x = self.lane_x + int(round(judge_rel_beat * beat_width))
            if is_active:
                self.last_judge_x = judge_x

        # Draw Measure Lines
        show_m_lines = getattr(opts, 'show_measure_lines', True) if opts else True
        if show_m_lines:
            for i in range(event_index, len(events)):
                event = events[i]
                if event.get('channel') != 'measure_line':
                    continue

                ev_beat = event.get('beat', 0.0)
                if ev_beat < start_beat:
                    continue
                if ev_beat >= end_beat + 1.0:
                    break

                if start_beat <= ev_beat < end_beat:
                    if use_fixed_judge:
                        m_x = judge_x + int(round((ev_beat - current_beat) * beat_width))
                    else:
                        m_x = self.lane_x + int(round((ev_beat - start_beat) * beat_width))

                    if self.lane_x <= m_x < self.lane_x + track_width:
                        for idx in range(self.lane_count):
                            offset = 1 if (self.is_dp and self.half > 0 and idx >= self.half) else 0
                            row_y = start_y + 1 + idx + offset
                            if row_y < bottom_y and row_y < max_y - 1:
                                self.safe_addstr(stdscr, row_y, m_x, "|", curses.A_DIM)

        # Draw Notes in active window
        for i in range(event_index, len(events)):
            event = events[i]
            channel = event.get('channel')
            if not channel or channel == 'measure_line':
                continue

            if not self.is_note_visible(event, current_time):
                continue

            lane_idx = self.get_lane_index(channel, player)
            if lane_idx is None or lane_idx >= self.lane_count:
                continue

            ev_beat = event.get('beat', 0.0)
            if ev_beat < start_beat:
                continue
            if ev_beat >= end_beat + 1.0:
                break

            if start_beat <= ev_beat < end_beat:
                if use_fixed_judge:
                    note_x = judge_x + int(round((ev_beat - current_beat) * beat_width))
                else:
                    note_x = self.lane_x + int(round((ev_beat - start_beat) * beat_width))

                if not (self.lane_x <= note_x < self.lane_x + track_width):
                    continue

                offset = 1 if (self.is_dp and self.half > 0 and lane_idx >= self.half) else 0
                row_y = start_y + 1 + lane_idx + offset

                if row_y < bottom_y and row_y < max_y - 1:
                    if event.get('is_mine'):
                        n_str = "!"
                        n_attr = curses.A_REVERSE
                    else:
                        ch = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
                        n_str = ch[0] if isinstance(ch, str) and len(ch) > 0 else "*"
                        n_attr = curses.A_BOLD if is_active else curses.A_NORMAL

                    self.safe_addstr(stdscr, row_y, note_x, n_str, n_attr)

        # Draw Long Notes (LN Bodies & Heads)
        for i in range(event_index, len(events)):
            event = events[i]
            if event.get('ln_state') != 'end':
                continue
            if not self.is_note_visible(event, current_time):
                continue

            start_ev = event.get('ln_partner')
            if not start_ev:
                continue

            channel = event.get('channel')
            lane_idx = self.get_lane_index(channel, player) if channel else None
            if lane_idx is None or lane_idx >= self.lane_count:
                continue

            s_beat = start_ev.get('beat', 0.0)
            e_beat = event.get('beat', 0.0)

            if e_beat < start_beat or s_beat > end_beat:
                continue

            offset = 1 if (self.is_dp and self.half > 0 and lane_idx >= self.half) else 0
            row_y = start_y + 1 + lane_idx + offset
            if row_y >= bottom_y or row_y >= max_y - 1:
                continue

            if use_fixed_judge:
                x_start_ln = judge_x + int(round((s_beat - current_beat) * beat_width))
                x_end_ln = judge_x + int(round((e_beat - current_beat) * beat_width))
            else:
                x_start_ln = self.lane_x + int(round(max(0.0, s_beat - start_beat) * beat_width))
                x_end_ln = self.lane_x + int(round(min(beats_per_window, e_beat - start_beat) * beat_width))

            # トラック領域内に収まる範囲でボディ描画
            draw_body_start = max(self.lane_x, x_start_ln + 1)
            draw_body_end = min(self.lane_x + track_width, x_end_ln)
            for x_b in range(draw_body_start, draw_body_end):
                self.safe_addstr(stdscr, row_y, x_b, "=", curses.A_BOLD if is_active else curses.A_NORMAL)

            ch = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
            head_char = ch[0] if isinstance(ch, str) and len(ch) > 0 else "*"

            if start_beat <= s_beat < end_beat and not start_ev.get('manual_hit') and (current_time < start_ev.get('time', 0.0)):
                if self.lane_x <= x_start_ln < self.lane_x + track_width:
                    self.safe_addstr(stdscr, row_y, x_start_ln, head_char, curses.A_BOLD if is_active else curses.A_NORMAL)

            if start_beat <= e_beat < end_beat:
                if self.lane_x <= x_end_ln < self.lane_x + track_width:
                    show_end = opts.show_ln_end_head if opts else False
                    end_char = head_char if show_end else "|"
                    self.safe_addstr(stdscr, row_y, x_end_ln, end_char, curses.A_BOLD if is_active else curses.A_NORMAL)

        # Draw Scanning Judgement Line (Playhead) - ONLY on Active Pane
        if is_active:
            if self.lane_x <= judge_x < self.lane_x + track_width:
                for idx in range(self.lane_count):
                    offset = 1 if (self.is_dp and self.half > 0 and idx >= self.half) else 0
                    row_y = start_y + 1 + idx + offset
                    if row_y < bottom_y and row_y < max_y - 1:
                        is_key_active = (idx < len(player.key_pressed_time)) and (current_time - player.key_pressed_time[idx] < 0.12)
                        j_attr = curses.A_REVERSE if is_key_active else (curses.A_BOLD | curses.A_STANDOUT)
                        self.safe_addstr(stdscr, row_y, judge_x, "|", j_attr)

    def render(self, stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play, opts, key_names, lane_chars, key_to_lane, use_pynput, get_key_events):
        draw_time = self.get_draw_time(current_time, opts)
        scale, player_height, current_bpm = self.calculate_scale_and_state(player, draw_time, initial_bpm, opts)

        # 高速ギミック判定（案1ベース: 初期BPMの100倍以上 または 10000以上）
        _init_bpm = getattr(player, 'initial_bpm', initial_bpm) or initial_bpm
        use_fixed_judge = (
            current_bpm >= _init_bpm * 100.0
            or current_bpm >= 10000.0
        )

        max_y, max_x = stdscr.getmaxyx()
        available_width = max(20, max_x - self.lane_x)

        # Header Info
        self.safe_addstr(stdscr, 0, 2, "Shinonome-Mini -- MixWaver Mode (2-Pane Alternating Scanning)", curses.A_BOLD)
        self.safe_addstr(stdscr, 1, 2, f"Song: {player.chart['info'].get('title', '___')} / Artist: {player.chart['info'].get('artist', '___')}")
        self.safe_addstr(stdscr, 2, 2, f"BPM: {current_bpm:.1f} | Time: {draw_time:.2f}s | HS: {opts.hispeed:.1f}")

        # Gauge & Score Header
        gauge_attr = curses.A_BOLD
        if player.hard_mode and player.gauge <= 30.0:
            gauge_attr |= curses.A_BLINK
        elif player.gauge >= 80.0:
            gauge_attr |= curses.A_STANDOUT
        self.safe_addstr(stdscr, 2, 45, f"GAUGE: {player.gauge:5.1f}%", gauge_attr)

        max_score = player.total_playable_notes * 2
        self.safe_addstr(stdscr, 2, 62, f"EX: {player.ex_score:4d}/{max_score:4d} | COMBO: {player.combo:4d}")

        # Calculate beat progression & measure windows for 2-pane alternating sweep
        beats_per_window = 4.0 / max(0.01, opts.hispeed)
        track_width = max(1, available_width - 1)
        beat_width = max(1.0, track_width / beats_per_window)

        current_beat = player_height
        measure_idx = int(current_beat // beats_per_window)

        if measure_idx % 2 == 0:
            # Even measure: Upper Pane is ACTIVE (Measure N), Lower Pane is PREVIEW (Measure N+1)
            active_pane = 'upper'
            start_beat_upper = measure_idx * beats_per_window
            start_beat_lower = (measure_idx + 1) * beats_per_window
        else:
            # Odd measure: Lower Pane is ACTIVE (Measure N), Upper Pane is PREVIEW (Measure N+1)
            active_pane = 'lower'
            start_beat_upper = (measure_idx + 1) * beats_per_window
            start_beat_lower = measure_idx * beats_per_window

        dp_extra = 1 if (self.is_dp and self.half > 0) else 0

        draw_start_idx = self.get_draw_start_index(events, draw_time, lookback_sec=10.0)

        # Render Upper Pane
        upper_start_y = 3
        m_num_upper = int(start_beat_upper // beats_per_window) + 1
        upper_title = f"UPPER PANE - Measure {m_num_upper}" + (" [ACTIVE]" if active_pane == 'upper' else " [PREVIEW]")
        self._render_pane(stdscr, upper_title, upper_start_y, start_beat_upper, beats_per_window,
                          beat_width, track_width, (active_pane == 'upper'), current_beat, draw_time,
                          events, draw_start_idx, player, lane_chars, opts, max_y, max_x,
                          use_fixed_judge=use_fixed_judge)

        # Render Lower Pane
        lower_start_y = upper_start_y + 2 + self.lane_count + dp_extra
        m_num_lower = int(start_beat_lower // beats_per_window) + 1
        lower_title = f"LOWER PANE - Measure {m_num_lower}" + (" [ACTIVE]" if active_pane == 'lower' else " [PREVIEW]")
        self._render_pane(stdscr, lower_title, lower_start_y, start_beat_lower, beats_per_window,
                          track_width=track_width, beat_width=beat_width, is_active=(active_pane == 'lower'),
                          current_beat=current_beat, current_time=draw_time,
                          events=events, event_index=draw_start_idx, player=player,
                          lane_chars=lane_chars, opts=opts, max_y=max_y, max_x=max_x,
                          use_fixed_judge=use_fixed_judge)

        # Footer Stats & Judgement Display
        footer_y = lower_start_y + 2 + self.lane_count + dp_extra
        if footer_y < max_y - 2:
            if player.last_judgement and (current_time - player.judgement_time < 0.5):
                j_text = f"[{player.last_judgement}]"
                self.safe_addstr(stdscr, footer_y, self.lane_x, j_text, curses.A_BOLD)
                if player.combo >= 3:
                    self.safe_addstr(stdscr, footer_y, self.lane_x + 15, f"{player.combo} COMBO!", curses.A_BOLD)

            stat_str = f"P:{player.perfect_count} G:{player.great_count} g:{player.good_count} B:{player.bad_count} M:{player.miss_count}"
            self.safe_addstr(stdscr, footer_y + 1, self.lane_x, stat_str, curses.A_DIM)

        # Handle Keyboard & Input Loop
        self.process_input(stdscr, player, auto_play, opts, key_to_lane, use_pynput, get_key_events)

