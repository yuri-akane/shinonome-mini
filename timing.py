import bisect
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

@dataclass
class TimelineSegment:
    start_time: float
    end_time: float
    start_beat: float
    end_beat: float
    start_height: float
    end_height: float
    bpm: float
    multiplier: float
    is_stop: bool = False

class BpmTimeline:
    """Utility to convert time (seconds) to beat position and cumulative visual height,
    handling BPM changes, measure multipliers, and STOP events.
    """
    def __init__(self, initial_bpm: float, bpm_events: List[Tuple[float, float]], 
                 stop_events: List[Tuple[float, float]], measures_multiplier: List[float]):
        """Create timeline segments.
        initial_bpm: starting BPM.
        bpm_events: list of (beat, bpm).
        stop_events: list of (beat, stop_value).
        measures_multiplier: list of float multipliers indexed by measure index.
        """
        self.initial_bpm = initial_bpm
        self.bpm_events = sorted(bpm_events, key=lambda x: x[0])
        self.stop_events = sorted(stop_events, key=lambda x: x[0])
        self.measures_multiplier = measures_multiplier
        
        # Calculate measure start beats
        self.measure_beats = [0.0] * (len(measures_multiplier) + 1)
        curr_beat = 0.0
        for i, mult in enumerate(measures_multiplier):
            self.measure_beats[i] = curr_beat
            curr_beat += 4.0 * mult
        self.measure_beats[len(measures_multiplier)] = curr_beat

        self.segments: List[TimelineSegment] = []
        self._build()

    def _get_measure_multiplier(self, beat: float) -> float:
        # Find which measure contains the beat
        idx = bisect.bisect_right(self.measure_beats, beat) - 1
        idx = max(0, min(idx, len(self.measures_multiplier) - 1))
        return self.measures_multiplier[idx]

    def _build(self):
        # Collect all unique transition beats
        transition_beats = set()
        transition_beats.add(0.0)
        for beat, _ in self.bpm_events:
            transition_beats.add(beat)
        for beat, _ in self.stop_events:
            transition_beats.add(beat)
        for b in self.measure_beats:
            transition_beats.add(b)
        
        sorted_beats = sorted(list(transition_beats))
        
        # Maps for quick lookup of events at specific beats
        bpm_map = dict(self.bpm_events)
        stop_map = dict(self.stop_events)
        
        curr_bpm = self.initial_bpm
        curr_time = 0.0
        curr_height = 0.0
        
        for i in range(len(sorted_beats) - 1):
            b_start = sorted_beats[i]
            b_end = sorted_beats[i+1]
            
            # Update active BPM if there is a change at b_start
            if b_start in bpm_map:
                curr_bpm = bpm_map[b_start]
                
            mult = self._get_measure_multiplier(b_start)
            
            delta_beat = b_end - b_start
            delta_time = delta_beat * (60.0 / curr_bpm)
            delta_height = delta_beat * 1.0 # ここでHSが実装できる(1.0のところの数値を変える)。
            
            # Add normal segment
            seg = TimelineSegment(
                start_time=curr_time,
                end_time=curr_time + delta_time,
                start_beat=b_start,
                end_beat=b_end,
                start_height=curr_height,
                end_height=curr_height + delta_height,
                bpm=curr_bpm,
                multiplier=mult,
                is_stop=False
            )
            self.segments.append(seg)
            
            curr_time += delta_time
            curr_height += delta_height
            
            # If there is a STOP event at b_end, insert a STOP segment
            if b_end in stop_map:
                # Update current BPM first if there's also a BPM change at b_end
                if b_end in bpm_map:
                    curr_bpm = bpm_map[b_end]
                stop_val = stop_map[b_end]
                # STOP duration (seconds) = (STOP値 / 192) * (240 / 現在のBPM)
                stop_time = (stop_val / 192.0) * (240.0 / curr_bpm)
                
                stop_seg = TimelineSegment(
                    start_time=curr_time,
                    end_time=curr_time + stop_time,
                    start_beat=b_end,
                    end_beat=b_end,
                    start_height=curr_height,
                    end_height=curr_height,
                    bpm=curr_bpm,
                    multiplier=mult,
                    is_stop=True
                )
                self.segments.append(stop_seg)
                curr_time += stop_time

        # Final segment for lookup beyond the last transition beat
        # Use a very large end_time and end_beat
        last_beat = sorted_beats[-1]
        if last_beat in bpm_map:
            curr_bpm = bpm_map[last_beat]
        mult = self._get_measure_multiplier(last_beat)
        
        final_seg = TimelineSegment(
            start_time=curr_time,
            end_time=curr_time + 1e6, # practically infinite
            start_beat=last_beat,
            end_beat=last_beat + 1e6,
            start_height=curr_height,
            end_height=curr_height + 1e6,
            bpm=curr_bpm,
            multiplier=mult,
            is_stop=False
        )
        self.segments.append(final_seg)

        # Precompute start times for bisect lookup
        self._segment_start_times = [s.start_time for s in self.segments]

        # Write timeline segment details to timing_debug.log
        # try:
        #     with open("timing_debug.log", "w", encoding="utf-8") as f:
        #         f.write(f"Initial BPM: {self.initial_bpm}\n")
        #         f.write("Timeline Segments:\n")
        #         for idx, seg in enumerate(self.segments):
        #             f.write(f"Segment {idx:03d}: Time [{seg.start_time:.3f} -> {seg.end_time:.3f}], "
        #                     f"Beat [{seg.start_beat:.3f} -> {seg.end_beat:.3f}], "
        #                     f"Height [{seg.start_height:.3f} -> {seg.end_height:.3f}], "
        #                     f"BPM: {seg.bpm:.1f}, Mult: {seg.multiplier:.3f}, Stop: {seg.is_stop}\n")
        # except Exception:
        #     pass

    def get_state(self, time_sec: float) -> Tuple[float, float, float, float]:
        """Given current time in seconds, return:
        (beat, cumulative_height, current_bpm, current_multiplier)
        """
        if time_sec <= 0.0:
            return 0.0, 0.0, self.initial_bpm, self._get_measure_multiplier(0.0)
            
        # Bisect to find the segment
        idx = bisect.bisect_right(self._segment_start_times, time_sec) - 1
        idx = max(0, min(idx, len(self.segments) - 1))
        seg = self.segments[idx]
        
        if seg.is_stop:
            return seg.start_beat, seg.start_height, 0.0, seg.multiplier
            
        # Linear interpolation
        duration = seg.end_time - seg.start_time
        if duration <= 0.0:
            return seg.start_beat, seg.start_height, seg.bpm, seg.multiplier
            
        fraction = (time_sec - seg.start_time) / duration
        beat = seg.start_beat + fraction * (seg.end_beat - seg.start_beat)
        height = seg.start_height + fraction * (seg.end_height - seg.start_height)
        return beat, height, seg.bpm, seg.multiplier

    def get_height_at_beat(self, beat: float) -> float:
        """Helper to get the cumulative height at a specific beat."""
        # Find segment by beat
        segment_start_beats = [s.start_beat for s in self.segments]
        idx = bisect.bisect_right(segment_start_beats, beat) - 1
        idx = max(0, min(idx, len(self.segments) - 1))
        seg = self.segments[idx]
        
        if seg.is_stop or seg.end_beat == seg.start_beat:
            return seg.start_height
            
        fraction = (beat - seg.start_beat) / (seg.end_beat - seg.start_beat)
        return seg.start_height + fraction * (seg.end_height - seg.start_height)

