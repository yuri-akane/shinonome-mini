import curses

def lane_info(mode: str) -> tuple[int, int]:
    """
    受け取ったモード文字列からレーン数と半分位置を返す。
    """
    if not isinstance(mode, str):
        mode = str(mode)
    mode = mode.upper()
    if mode in ('10K', '14K'):
        return (16 if mode == '14K' else 12,
                8 if mode == '14K' else 6)
    if mode == '9K':
        return 9, 0
    if mode in ('6K', '5K'):
        return 6, 0
    if mode == '4K':
        return 4, 0
    # デフォルトは7K（8レーン）
    return 8, 0


class BaseRenderer:
    """Base class for UI Renderers."""

    def lane_info(self, mode: str = None) -> tuple[int, int]:
        """レーン数と半分位置を返す。"""
        m = mode if mode is not None else getattr(self, 'mode', '7K')
        return lane_info(m)


    def calculate_y(self, event, player, judgement_y, player_height, scale):
        """Calculate drawn Y coordinate and target seconds from event time/beat."""
        target_seconds = event['time']
        if getattr(player, 'timeline', None):
            note_height = player.timeline.get_height_at_beat(event['beat'])
        else:
            note_height = target_seconds
        y = judgement_y - int((note_height - player_height) * scale)
        return y, target_seconds

    def get_lane_index(self, channel, player):
        """Determine lane index from channel name."""
        if channel in player.channel_to_lane:
            return player.channel_to_lane[channel]

        # Extended channel (51-69) handling
        if channel.isdigit() and 51 <= int(channel) <= 69:
            base_chan = str(int(channel) - 40)
            return player.channel_to_lane.get(base_chan)

        return None

    def safe_addstr(self, stdscr, y: int, x: int, text: str, attr=curses.A_NORMAL):
        """Safely print text to stdscr without raising curses.error when clipping boundaries."""
        try:
            max_y, max_x = stdscr.getmaxyx()
            if 0 <= y < max_y and 0 <= x < max_x:
                stdscr.addstr(y, x, text[:max_x - x], attr)
        except curses.error:
            pass

    def get_draw_time(self, current_time: float, opts) -> float:
        """Calculate display/drawing time reflecting note_display_offset_ms."""
        offset_sec = getattr(opts, 'note_display_offset_ms', 0) / 1000.0
        return current_time - offset_sec

    def get_draw_start_index(self, events: list, draw_time: float, lookback_sec: float = 2.0) -> int:
        """Find the starting event index to iterate based on draw_time."""
        target_time = max(0.0, draw_time - lookback_sec)
        # Binary search for the first event with time >= target_time
        left = 0
        right = len(events)
        while left < right:
            mid = (left + right) // 2
            if events[mid].get('time', 0.0) < target_time:
                left = mid + 1
            else:
                right = mid
        return left

    def is_note_visible(self, event: dict, draw_time: float) -> bool:
        """Determine if a note should be rendered at the current draw_time."""
        # Manual hits (player pressed key and hit) are immediately hidden
        if event.get('manual_hit'):
            return False
        # Missed notes that expired are hidden
        if event.get('state') == 2:
            return False

        # Long note partner check
        if event.get('ln_state') == 'end':
            start_ev = event.get('ln_partner')
            if start_ev and start_ev.get('manual_hit') and event.get('state') == 1:
                return False
            # Visible if end hasn't passed judgment line plus flash window
            return (draw_time - event.get('time', 0.0)) < 0.08

        # Standard notes: visible until passed judgment line plus flash duration
        target_time = event.get('time', 0.0)
        return (draw_time - target_time) < 0.08

    def calculate_scale_and_state(self, player, draw_time, initial_bpm, opts, base_speed=22.0):
        """Calculate scale, player_height, and current_bpm from timeline or fallback using draw_time."""
        speed = base_speed * opts.hispeed
        if getattr(player, 'timeline', None):
            beat_duration = 60.0 / player.initial_bpm
            scale = speed * beat_duration
            _, player_height, current_bpm, _ = player.timeline.get_state(draw_time)
        else:
            scale = speed
            player_height = draw_time
            current_bpm = getattr(player, 'current_bpm', initial_bpm)
        return scale, player_height, current_bpm

    def process_input(self, stdscr, player, auto_play, opts, key_to_lane, use_pynput, get_key_events):
        """Handle curses key input and pynput background events."""
        while True:
            ch = stdscr.getch()
            if ch == -1:
                break
            if ch == opts.quit_key_code:
                player.is_playing = False
                continue
            if ch in key_to_lane:
                if not auto_play:
                    player.press_key(key_to_lane[ch])
                continue
            if ch == opts.speedup_code:
                opts.hispeed = min(opts.hispeed + 0.2, 100.0)
            elif ch == opts.speeddown_code:
                opts.hispeed = max(opts.hispeed - 0.2, 0.2)

        key_events = get_key_events() if (use_pynput and get_key_events) else []
        for ev_type, k in key_events:
            if ev_type != "press" or not k:
                continue
            if k.startswith("'") and k.endswith("'") and len(k) >= 3:
                k = k[1:-1]
            if k.startswith("Key."):
                k = k[4:]
            #mod_keys = settings.get('modifier_keys', {})
            #↓冗長すぎるので要修正
            mode = player.chart.get('mode', '7K').upper() if getattr(player, 'chart', None) else '7K'
            mod_keys = opts.load_modifier_keys(mode=mode, scratch_side=opts.scratch_side)
            if k in mod_keys:
                if not auto_play:
                    player.press_key(mod_keys[k])
                continue

    def render(self, stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play, opts, key_names, lane_chars, key_to_lane, use_pynput, get_key_events):
        """Render loop callback to be implemented by subclasses."""
        raise NotImplementedError

