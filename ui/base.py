import curses

class BaseRenderer:
    """Base class for UI Renderers."""

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

    def render(self, stdscr, player, current_time, events, event_index, initial_bpm, resolution, auto_play, settings, key_names, lane_chars, quit_key_code, key_to_lane, speedup_keycode, speeddown_keycode, use_pynput, get_key_events):
        """Render loop callback to be implemented by subclasses."""
        raise NotImplementedError
