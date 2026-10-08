import curses
import bisect
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
        self.frozen_active_pane: str | None = None  # 'upper' or 'lower'。None=通常モード
        self.frozen_judge_x: int = self.lane_x      # ギミック突入時の judge_x を凍結
        self.frozen_start_beat_upper: float = 0.0   # ギミック突入時のUpper小節開始ビート
        self.frozen_start_beat_lower: float = 0.0   # ギミック突入時のLower小節開始ビート
        self.frozen_beat: float = 0.0               # ギミック突入時の基準ビート
        self.visual_beat_offset: float = 0.0        # ギミック終了後の表示ビート補正量
        self.last_current_beat: float = 0.0         # 前フレームのbeat位置（速度検出用）
        self.last_time_sec: float | None = None     # 前フレームの時刻
        self.last_active_pane: str = 'upper'        # 前フレームの正常active_pane（凍結先決定用）
        self.last_start_beat_upper: float = 0.0     # 前フレームのUpper小節開始ビート
        self.last_start_beat_lower: float = 0.0     # 前フレームのLower小節開始ビート


    def _render_pane(self, stdscr, pane_title: str, start_y: int, start_beat: float, beats_per_window: float,
                     beat_width: float, track_width: int, is_active: bool, current_beat: float, current_time: float,
                     events: list, event_index: int, player, lane_chars, opts, max_y: int, max_x: int,
                     key_names: list = None, use_fixed_judge: bool = False,
                     flipbook_partner_pane: bool = False, partner_offset_beats: float = 0.0,
                     visual_beat_offset: float = 0.0):

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

            label = (key_names[idx] if (key_names and idx < len(key_names)) else f"[L{idx}]")
            is_key_active = (idx < len(player.key_pressed_time)) and (current_time - player.key_pressed_time[idx] < 0.12)
            label_attr = curses.A_REVERSE if is_key_active else (curses.A_BOLD if is_active else curses.A_NORMAL)
            self.safe_addstr(stdscr, row_y, 1, f"{label:^5s}", label_attr)

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

        # 判定ラインX座標の決定（高速ギミック時は凍結座標、通常時は進行beatに応じた位置）
        if use_fixed_judge:
            judge_x = self.frozen_judge_x
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
                if use_fixed_judge:
                    if ev_beat < current_beat - beats_per_window:
                        continue
                    if ev_beat > current_beat + beats_per_window * 2:
                        break
                    if flipbook_partner_pane:
                        m_x = self.lane_x + int(round((ev_beat - current_beat - partner_offset_beats) * beat_width))
                    else:
                        m_x = judge_x + int(round((ev_beat - current_beat) * beat_width))
                else:
                    disp_m_beat = ev_beat - visual_beat_offset
                    if disp_m_beat < start_beat:
                        continue
                    if disp_m_beat >= end_beat + 1.0:
                        break
                    if start_beat <= disp_m_beat < end_beat:
                        m_x = self.lane_x + int(round((disp_m_beat - start_beat) * beat_width))
                    else:
                        continue

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
            if use_fixed_judge:
                if ev_beat < current_beat - beats_per_window:
                    continue
                if ev_beat > current_beat + beats_per_window * 2:
                    break
                if flipbook_partner_pane:
                    note_x = self.lane_x + int(round((ev_beat - current_beat - partner_offset_beats) * beat_width))
                else:
                    note_x = judge_x + int(round((ev_beat - current_beat) * beat_width))
            else:
                disp_ev_beat = ev_beat - visual_beat_offset
                if disp_ev_beat < start_beat:
                    continue
                if disp_ev_beat >= end_beat + 1.0:
                    break
                if start_beat <= disp_ev_beat < end_beat:
                    note_x = self.lane_x + int(round((disp_ev_beat - start_beat) * beat_width))
                else:
                    continue

            if not (self.lane_x <= note_x < self.lane_x + track_width):
                continue

            # MW: 判定ラインを通過した位置のノートは非表示（アクティブペインのみ）
            if is_active and note_x < judge_x:
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
                    n_attr = curses.A_BOLD if (is_active or use_fixed_judge) else curses.A_NORMAL

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

            if use_fixed_judge:
                if e_beat < current_beat - beats_per_window:
                    continue
                if s_beat > current_beat + beats_per_window * 2:
                    continue
            else:
                disp_s_beat = s_beat - visual_beat_offset
                disp_e_beat = e_beat - visual_beat_offset
                if disp_e_beat < start_beat or disp_s_beat > end_beat:
                    continue

            offset = 1 if (self.is_dp and self.half > 0 and lane_idx >= self.half) else 0
            row_y = start_y + 1 + lane_idx + offset
            if row_y >= bottom_y or row_y >= max_y - 1:
                continue

            if use_fixed_judge:
                if flipbook_partner_pane:
                    x_start_ln = self.lane_x + int(round((s_beat - current_beat - partner_offset_beats) * beat_width))
                    x_end_ln   = self.lane_x + int(round((e_beat - current_beat - partner_offset_beats) * beat_width))
                else:
                    x_start_ln = judge_x + int(round((s_beat - current_beat) * beat_width))
                    x_end_ln   = judge_x + int(round((e_beat - current_beat) * beat_width))
            else:
                disp_s_beat = s_beat - visual_beat_offset
                disp_e_beat = e_beat - visual_beat_offset
                x_start_ln = self.lane_x + int(round(max(0.0, disp_s_beat - start_beat) * beat_width))
                x_end_ln   = self.lane_x + int(round(min(beats_per_window, disp_e_beat - start_beat) * beat_width))

            # トラック領域内に収まる範囲でボディ描画
            draw_body_start = max(self.lane_x, x_start_ln + 1)
            draw_body_end = min(self.lane_x + track_width, x_end_ln)
            # MW: 判定ライン通過済みのLNボディは非表示（アクティブペインのみ）
            if is_active:
                draw_body_start = max(draw_body_start, judge_x + 1)
            for x_b in range(draw_body_start, draw_body_end):
                self.safe_addstr(stdscr, row_y, x_b, "=", curses.A_BOLD if (is_active or use_fixed_judge) else curses.A_NORMAL)

            ch = lane_chars.get(lane_idx, "*") if isinstance(lane_chars, dict) else lane_chars[lane_idx]
            head_char = ch[0] if isinstance(ch, str) and len(ch) > 0 else "*"

            # LNヘッド：ギミック時はBeat範囲条件をX座標範囲で代替
            disp_s = s_beat if use_fixed_judge else (s_beat - visual_beat_offset)
            disp_e = e_beat if use_fixed_judge else (e_beat - visual_beat_offset)
            show_head = (
                (use_fixed_judge or (start_beat <= disp_s < end_beat))
                and not start_ev.get('manual_hit')
                and (current_time < start_ev.get('time', 0.0))
            )
            if show_head:
                if self.lane_x <= x_start_ln < self.lane_x + track_width:
                    # MW: 判定ライン通過済みのLNヘッドは非表示（アクティブペインのみ）
                    if not (is_active and x_start_ln < judge_x):
                        self.safe_addstr(stdscr, row_y, x_start_ln, head_char, curses.A_BOLD if (is_active or use_fixed_judge) else curses.A_NORMAL)

            show_tail = use_fixed_judge or (start_beat <= disp_e < end_beat)
            if show_tail:
                if self.lane_x <= x_end_ln < self.lane_x + track_width:
                    show_end = opts.show_ln_end_head if opts else False
                    end_char = head_char if show_end else "|"
                    self.safe_addstr(stdscr, row_y, x_end_ln, end_char, curses.A_BOLD if (is_active or use_fixed_judge) else curses.A_NORMAL)

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
        display_beat = current_beat - self.visual_beat_offset

        # --- 判定ライン移動速度および高速BPMギミック検出 ---
        # 1. タイムラインセグメントの現在BPM判定（STOP中や超高速セグメントの安定検出）
        _init_bpm = getattr(player, 'initial_bpm', initial_bpm) or initial_bpm
        seg_bpm = current_bpm
        if getattr(player, 'timeline', None) and getattr(player.timeline, 'segments', None):
            tl = player.timeline
            if tl._segment_start_times:
                idx = bisect.bisect_right(tl._segment_start_times, draw_time) - 1
                idx = max(0, min(idx, len(tl.segments) - 1))
                seg_bpm = tl.segments[idx].bpm

        is_high_bpm = (seg_bpm >= _init_bpm * 100.0 or seg_bpm >= 10000.0)

        # 2. 1フレームあたりの変化速度判定（急激な変化）
        dt = (draw_time - self.last_time_sec) if self.last_time_sec is not None else 0.0
        delta_beat = abs(current_beat - self.last_current_beat) if self.last_time_sec is not None else 0.0
        delta_judge_px = delta_beat * beat_width
        speed_threshold_px = max(10.0, track_width * 0.25)
        is_fast_jump = (delta_judge_px >= speed_threshold_px) or (delta_beat >= beats_per_window * 0.4)

        # どちらかを満たすか、あるいは一度凍結された後で急変状態が収まるまではギミックモードを維持
        use_fixed_judge = is_high_bpm or is_fast_jump or (self.frozen_active_pane is not None and is_high_bpm)

        # 通常スキャン小節計算（表示用 display_beat を基準）
        measure_idx = int(display_beat // beats_per_window)
        if measure_idx % 2 == 0:
            active_pane = 'upper'
            start_beat_upper = measure_idx * beats_per_window
            start_beat_lower = (measure_idx + 1) * beats_per_window
        else:
            active_pane = 'lower'
            start_beat_upper = (measure_idx + 1) * beats_per_window
            start_beat_lower = measure_idx * beats_per_window

        dp_extra = 1 if (self.is_dp and self.half > 0) else 0

        # --- Flipbook凍結管理 ---
        if use_fixed_judge:
            if self.frozen_active_pane is None:
                # ギミック突入: 直前の正常フレームでのPane、判定ライン、小節開始位置を凍結
                self.frozen_active_pane = self.last_active_pane
                self.frozen_judge_x = self.last_judge_x
                self.frozen_start_beat_upper = self.last_start_beat_upper
                self.frozen_start_beat_lower = self.last_start_beat_lower
                self.frozen_beat = self.last_current_beat
            # ギミック中は小節番号・基準ビートも凍結時の値に固定し、Paneタイトルの目まぐるしい反転やズレを防ぐ
            disp_start_beat_upper = self.frozen_start_beat_upper
            disp_start_beat_lower = self.frozen_start_beat_lower
            upper_is_active = (self.frozen_active_pane == 'upper')
            lower_is_active = (self.frozen_active_pane == 'lower')
            upper_flipbook_partner = not upper_is_active
            lower_flipbook_partner = not lower_is_active
            pass_beat = current_beat
        else:
            # ギミック終了（通常スキャンへ復帰）
            if self.frozen_active_pane is not None:
                # 終了の瞬間: 凍結されていた位置からそのままスキャンが再開するようにオフセットを確定
                self.visual_beat_offset += (current_beat - self.frozen_beat)
                self.frozen_active_pane = None
                display_beat = current_beat - self.visual_beat_offset
                measure_idx = int(display_beat // beats_per_window)
                if measure_idx % 2 == 0:
                    active_pane = 'upper'
                    start_beat_upper = measure_idx * beats_per_window
                    start_beat_lower = (measure_idx + 1) * beats_per_window
                else:
                    active_pane = 'lower'
                    start_beat_upper = (measure_idx + 1) * beats_per_window
                    start_beat_lower = measure_idx * beats_per_window

            disp_start_beat_upper = start_beat_upper
            disp_start_beat_lower = start_beat_lower
            upper_is_active = (active_pane == 'upper')
            lower_is_active = (active_pane == 'lower')
            upper_flipbook_partner = False
            lower_flipbook_partner = False
            pass_beat = display_beat

        draw_start_idx = self.get_draw_start_index(events, draw_time, lookback_sec=10.0)

        # Render Upper Pane
        upper_start_y = 3
        m_num_upper = int(disp_start_beat_upper // beats_per_window) + 1
        upper_title = f"UPPER PANE - Measure {m_num_upper}" + (" [ACTIVE]" if upper_is_active else " [PREVIEW]")
        self._render_pane(stdscr, upper_title, upper_start_y, disp_start_beat_upper, beats_per_window,
                          beat_width, track_width, upper_is_active, pass_beat, draw_time,
                          events, draw_start_idx, player, lane_chars, opts, max_y, max_x,
                          key_names=key_names, use_fixed_judge=use_fixed_judge,
                          flipbook_partner_pane=upper_flipbook_partner,
                          partner_offset_beats=beats_per_window,
                          visual_beat_offset=self.visual_beat_offset)

        # Render Lower Pane
        lower_start_y = upper_start_y + 2 + self.lane_count + dp_extra
        m_num_lower = int(disp_start_beat_lower // beats_per_window) + 1
        lower_title = f"LOWER PANE - Measure {m_num_lower}" + (" [ACTIVE]" if lower_is_active else " [PREVIEW]")
        self._render_pane(stdscr, lower_title, lower_start_y, disp_start_beat_lower, beats_per_window,
                          track_width=track_width, beat_width=beat_width, is_active=lower_is_active,
                          current_beat=pass_beat, current_time=draw_time,
                          events=events, event_index=draw_start_idx, player=player,
                          lane_chars=lane_chars, opts=opts, max_y=max_y, max_x=max_x,
                          key_names=key_names, use_fixed_judge=use_fixed_judge,
                          flipbook_partner_pane=lower_flipbook_partner,
                          partner_offset_beats=beats_per_window,
                          visual_beat_offset=self.visual_beat_offset)

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

        # 次フレームの速度計算・凍結判定用に通常状態を更新（通常時のみ最新状態を記録）
        if not use_fixed_judge:
            self.last_active_pane = active_pane
            self.last_start_beat_upper = start_beat_upper
            self.last_start_beat_lower = start_beat_lower
        self.last_current_beat = current_beat
        self.last_time_sec = draw_time

        # Handle Keyboard & Input Loop
        self.process_input(stdscr, player, auto_play, opts, key_to_lane, use_pynput, get_key_events)

