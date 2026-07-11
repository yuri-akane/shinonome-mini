import json
import os
import re

from typing import Dict, List, Tuple, Any
import logging
from constants import CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT
from timing import BpmTimeline, stop_seconds, estimated_total

class BmsParser:
    """Parse BMS files into a structured chart representation.
    The parser extracts header information, wav table, measure multipliers,
    and builds a list of timed events.
    """
    def __init__(self):
        self.header_re = re.compile(r"^#(\w+)\s+(.+)")
        self.data_re = re.compile(r"^#(\d{3})(\d{2}):(.+)")

    def _parse_header(self, line: str, info: dict, wav_table: dict) -> None:
        """Parse a header line and update info or wav_table.
        Args:
            line: The raw line string starting with '#'.
            info: Dictionary accumulating song metadata.
            wav_table: Dictionary mapping wav IDs to file paths.
        """
        header_match = self.header_re.match(line)
        if not header_match:
            return
        key, val = header_match.groups()
        key_upper = key.upper()
        if key_upper == "TITLE":
            info['title'] = val
        elif key_upper == "ARTIST":
            info['artist'] = val
        elif key_upper == "BPM":
            try:
                info['bpm'] = float(val)
            except Exception:
                pass
        elif key_upper.startswith("BPM") and len(key_upper) > 3:
            id_36 = key_upper[3:].upper()
            try:
                info['bpm_table'][id_36] = float(val)
            except Exception:
                pass
        elif key_upper.startswith("STOP") and len(key_upper) > 4:
            id_36 = key_upper[4:].upper()
            try:
                info['stop_table'][id_36] = float(val)
            except Exception:
                pass
        elif key_upper == "RANK":
            try:
                info['rank'] = int(val)
            except Exception:
                pass
        elif key_upper == "LNOBJ":
            info['lnobj'] = val.upper()
        elif key_upper == "LNTYPE":
            try:
                info['lntype'] = int(val)
            except Exception:
                pass
        elif key_upper == "LNMODE":
            try:
                info['lnmode'] = int(val)
            except Exception:
                pass
        elif key_upper.startswith("WAV"):
            wav_id = key_upper[3:].upper()
            wav_table[wav_id] = val

    def _parse_data(self, line: str, measures_multiplier: list, raw_data: list) -> None:
        """Parse a data line (#measurechannel:data) and update measure multiplier or raw data.
        Args:
            line: The raw line string.
            measures_multiplier: List of beat multipliers per measure.
            raw_data: Accumulator for note data tuples.
        """
        data_match = self.data_re.match(line)
        if not data_match:
            return
        measure, channel, data_str = data_match.groups()
        measure_idx = int(measure)
        if channel == "02":
            try:
                multiplier = float(data_str)
                if multiplier > 0 and 0 <= measure_idx < 1000:
                    measures_multiplier[measure_idx] = multiplier
            except Exception:
                pass
            return
        skip_channels = {"04", "05", "06", "07", "0A", "0B", "0C", "0D", "0E", "0F"}
        if channel in skip_channels:
            return
        raw_data.append((measure_idx, channel, data_str))

    def parse(self, file_path: str) -> dict:
        """Parse a BMS file and return a structured chart dict.
        The method builds header info, wav table, measures multiplier, raw data,
        then computes beat timings and converts them to absolute seconds.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"BMS file not found: {file_path}")

    def parse(self, file_path: str) -> dict:
        """Parse a BMS file and return a structured chart dict.
        The method builds header info, wav table, measures multiplier, raw data,
        then computes beat timings and converts them to absolute seconds.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"BMS file not found: {file_path}")

        info = {
            'title': '',
            'artist': '',
            'bpm': 130.0,
            'rank': 3,
            'total': None,
            'bpm_table': {},
            'stop_table': {},
            'lnobj': None,
            'lntype': 1,
            'lnmode': 1
        }
        wav_table = {}
        measures_multiplier = [1.0] * 1000
        raw_data = []

        # BMSは一般的にShift-JISまたはCP932が多い
        with open(file_path, 'r', encoding='shift-jis', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('#'): continue

                # Determine if line is a header or data and delegate parsing
                header_match = self.header_re.match(line)
                if header_match:
                    # Use helper to parse header line
                    self._parse_header(line, info, wav_table)
                    continue
                # If not a header, try parsing as data line
                data_match = self.data_re.match(line)
                if data_match:
                    # Use helper to parse data line
                    self._parse_data(line, measures_multiplier, raw_data)
                # otherwise ignore line

        current_beat = 0.0
        measure_beats = [0.0] * 1000
        for i in range(1000):
            measure_beats[i] = current_beat
            current_beat += 4.0 * measures_multiplier[i]

        ln_channels = {
            "51", "52", "53", "54", "55", "56", "57", "58", "59",
            "61", "62", "63", "64", "65", "66", "67", "68", "69"
        }

        # 拍単位での各イベントの beat 値の算出
        events = []
        for measure, channel, data_str in raw_data:
            # If lntype == 2, skip LN channels here to process them separately
            if info['lntype'] == 2 and channel in ln_channels:
                continue

            objects = [data_str[i:i+2] for i in range(0, len(data_str), 2)]
            n = len(objects)
            for i, obj in enumerate(objects):
                if obj == "00": continue
                # Calculate beat position within the measure
                beat = measure_beats[measure] + (i / n) * 4.0 * measures_multiplier[measure]

                bpm_val = None
                stop_val = None
                if channel == "03":
                    # 16進数の値がそのままBPM値
                    try:
                        bpm_val = float(int(obj, 16))
                    except:
                        pass
                elif channel == "08":
                    # 拡張BPMテーブル（36進数定義）から参照
                    ref_key = obj.upper()
                    if ref_key in info['bpm_table']:
                        bpm_val = info['bpm_table'][ref_key]
                elif channel == "09":
                    # STOPテーブルから参照
                    ref_key = obj.upper()
                    if ref_key in info['stop_table']:
                        stop_val = info['stop_table'][ref_key]

                event_data = {
                    'beat': beat,
                    'time': 0.0, # あとで秒数に変換して上書きする
                    'sound_id': obj,
                    'channel': channel
                }
                if bpm_val is not None:
                    event_data['bpm'] = bpm_val
                if stop_val is not None:
                    event_data['stop'] = stop_val
                events.append(event_data)

        # Process LNTYPE 2 channels separately
        if info['lntype'] == 2:
            for ch in ln_channels:
                channel_data = [rd for rd in raw_data if rd[1] == ch]
                if not channel_data:
                    continue
                grid = []
                for measure, channel, data_str in channel_data:
                    objects = [data_str[i:i+2] for i in range(0, len(data_str), 2)]
                    n = len(objects)
                    for i, obj in enumerate(objects):
                        beat = measure_beats[measure] + (i / n) * 4.0 * measures_multiplier[measure]
                        grid.append((beat, obj))
                # Sort grid by beat
                grid.sort(key=lambda x: x[0])

                in_ln = False
                start_event = None
                for beat, obj in grid:
                    if not in_ln:
                        if obj != "00":
                            start_event = {
                                'beat': beat,
                                'time': 0.0,
                                'sound_id': obj,
                                'channel': ch,
                                'ln_state': 'start'
                            }
                            events.append(start_event)
                            in_ln = True
                    else:
                        if obj == "00":
                            end_event = {
                                'beat': beat,
                                'time': 0.0,
                                'sound_id': start_event['sound_id'],
                                'channel': ch,
                                'ln_state': 'end'
                            }
                            events.append(end_event)
                            in_ln = False
                if in_ln and start_event and grid:
                    end_event = {
                        'beat': grid[-1][0],
                        'time': 0.0,
                        'sound_id': start_event['sound_id'],
                        'channel': ch,
                        'ln_state': 'end'
                    }
                    events.append(end_event)

        # Mark LNTYPE 1 pairs (handle possible empty cells)
        if info['lntype'] == 1:
            for ch in ln_channels:
                # extract events for this channel and sort by beat
                ch_events = [ev for ev in events if ev.get('channel') == ch]
                ch_events.sort(key=lambda x: x['beat'])
                pending_start = None
                for ev in ch_events:
                    # skip notes that already have a ln_state (e.g., from LNOBJ handling)
                    if ev.get('ln_state') is not None:
                        continue
                    if pending_start is None:
                        # this note becomes the start of a long note
                        ev['ln_state'] = 'start'
                        pending_start = ev
                    else:
                        # this note closes the pending start
                        ev['ln_state'] = 'end'
                        pending_start = None
                # if a start remains without an end, it stays as a start (open long note)

        # Mark LNOBJ pairs
        if info['lnobj']:
            normal_channels = {
                "11", "12", "13", "14", "15", "16", "17", "18", "19",
                "21", "22", "23", "24", "25", "26", "27", "28", "29"
            }
            ch_events_map = {}
            for ev in events:
                ch = ev.get('channel')
                if ch in normal_channels:
                    ch_events_map.setdefault(ch, []).append(ev)
            for ch, ch_evs in ch_events_map.items():
                ch_evs.sort(key=lambda x: x['beat'])
                for idx, ev in enumerate(ch_evs):
                    if ev['sound_id'].upper() == info['lnobj']:
                        if idx > 0:
                            prev_ev = ch_evs[idx - 1]
                            if prev_ev.get('ln_state') is None:
                                prev_ev['ln_state'] = 'start'
                                ev['ln_state'] = 'end'

        # Add measure length change events for UI speed factor handling
        for idx, mult in enumerate(measures_multiplier):
            if mult != 1.0:
                # Create a control event at the start of the measure
                event_data = {
                    'beat': measure_beats[idx],
                    'time': 0.0,  # will be filled in later conversion loop
                    'channel': '02',
                    'measure_mult': mult
                }
                events.append(event_data)

        # Add visual measure lines at the start of each measure
        max_beat = 0.0
        if events:
            max_beat = max(ev['beat'] for ev in events)
        for idx, m_start_beat in enumerate(measure_beats):
            if m_start_beat > max_beat:
                break
            events.append({
                'beat': m_start_beat,
                'time': 0.0,
                'channel': 'measure_line',
                'measure_idx': idx
            })

        # beat順およびチャンネルプライオリティ順にソートする
        # BPM変更は同じbeatにある音符より先に評価し、STOPは音符が再生された後に停止するため音符より後に評価するべき
        def get_event_priority(ev):
            ch = ev.get('channel', 'XX')
            if ch in ("03", "08"): return 0  # BPM change first
            if ch == "measure_line": return 1.5
            if ch == "09": return 3          # STOP last (after note channels at 2)
            return 2                         # Notes / Sound channels last

        events.sort(key=lambda x: (x['beat'], get_event_priority(x)))
        
        # 時系列順（beat順）にBPM変化とSTOPコマンドを適用しながら累積経過時間を計算する。
        current_sec = 0.0
        prev_beat = 0.0
        current_bpm = info['bpm']

        for ev in events:
            ev_beat = ev['beat']
            delta_beat = ev_beat - prev_beat
            if delta_beat > 0:
                #逐次足しているので誤差が蓄積しうる処理。
                current_sec += delta_beat * (60.0 / current_bpm)
            
            ev['time'] = current_sec
            
            # 制御命令の状態の適用
            if 'bpm' in ev:
                current_bpm = ev['bpm']
            if 'stop' in ev:
                stop_sec = stop_seconds(ev['stop'], current_bpm)
                #逐次足しているので誤差が蓄積しうる処理。
                current_sec += stop_sec
                
            prev_beat = ev_beat

        # Resolve LN partners
        ln_by_channel = {}
        for ev in events:
            if 'ln_state' in ev:
                ch = ev['channel']
                norm_ch = ch
                if ch.startswith('5'):
                    norm_ch = '1' + ch[1:]
                elif ch.startswith('6'):
                    norm_ch = '2' + ch[1:]
                ln_by_channel.setdefault(norm_ch, []).append(ev)

        for norm_ch, evs in ln_by_channel.items():
            evs.sort(key=lambda x: x['beat'])
            start_ev = None
            for ev in evs:
                if ev['ln_state'] == 'start':
                    start_ev = ev
                elif ev['ln_state'] == 'end' and start_ev is not None:
                    start_ev['ln_partner_beat'] = ev['beat']
                    start_ev['ln_partner_time'] = ev['time']
                    start_ev['ln_partner'] = ev
                    ev['ln_partner_beat'] = start_ev['beat']
                    ev['ln_partner_time'] = start_ev['time']
                    ev['ln_partner'] = start_ev
                    start_ev = None

        # If #TOTAL is missing or non‑positive, estimate a sensible default.
        if not isinstance(info.get('total'), (int, float)) or info['total'] <= 0:
            # プレイ可能なノーツのみをカウント（チャンネル03/08/09や01のBGMを除いた、11〜29などのレーンチャンネル）
            # LNの終端はカウントしないようにする
            playable_channels = {
                "11", "12", "13", "14", "15", "16", "17", "18", "19",
                "21", "22", "23", "24", "25", "26", "27", "28", "29"
            }
            note_count = 0
            for ev in events:
                ch = ev.get('channel')
                if ch in playable_channels:
                    # If LNOBJ, the end note has ln_state == 'end', so do not count it
                    if ev.get('ln_state') == 'end':
                        continue
                    note_count += 1
                elif ch in ln_channels and ev.get('ln_state') == 'start':
                    note_count += 1
            info['total'] = estimated_total(note_count)

        # Construct BpmTimeline
        bpm_timeline_events = []
        stop_timeline_events = []
        for ev in events:
            if 'bpm' in ev:
                bpm_timeline_events.append((ev['beat'], ev['bpm']))
            if 'stop' in ev:
                stop_timeline_events.append((ev['beat'], ev['stop']))
                
        timeline = BpmTimeline(
            initial_bpm=info['bpm'],
            bpm_events=bpm_timeline_events,
            stop_events=stop_timeline_events,
            measures_multiplier=measures_multiplier
        )

        # Generate default channel_to_lane mapping based on mode and scratch side (default left)
        mode = info.get('mode', 'SP')
        # Choose mapping based on mode and default scratch side (left for SP)
        if mode == 'DP':
            # DP uses left mapping for both players (as in main)
            channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        else:
            # SP default to left side mapping
            channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        
        # Add long note channels mapping dynamically
        ln_mapping = {}
        for ch, lane in channel_to_lane.items():
            if ch.startswith('1'):
                ln_mapping['5' + ch[1:]] = lane
            elif ch.startswith('2'):
                ln_mapping['6' + ch[1:]] = lane
        channel_to_lane.update(ln_mapping)

        # Attach to chart result
        chart_channel_to_lane = channel_to_lane

        return {
            'info': info,
            'wav_table': wav_table,
            'events': events,
            'base_path': os.path.dirname(file_path),
            'timeline': timeline,
            'channel_to_lane': chart_channel_to_lane
        }

class BmsonParser:
    def __init__(self):
        pass

    def parse(self, file_path: str) -> dict:
        """bmsonファイルをパースして内部形式に変換する"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"bmson file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 抽出する基本情報
        info_data = data.get('info', {})
        resolution = info_data.get('resolution', 480)
        if not isinstance(resolution, (int, float)) or resolution <= 0:
            resolution = 480

        # Determine mode: if any note uses x >= 9, it's DP, else SP
        is_dp = False
        for channel in data.get('sound_channels', []):
            for note in channel.get('notes', []):
                x = note.get('x')
                if x is not None and 9 <= x <= 16:
                    is_dp = True
                    break
            if is_dp:
                break

        song_info = {
            'title': info_data.get('title', 'Unknown'),
            'artist': info_data.get('artist', 'Unknown'),
            'bpm': info_data.get('init_bpm', info_data.get('bpm', 130.0)),
            'rank': info_data.get('judge_rank', 3),
            'total': info_data.get('total', None),
            'bpm_table': {},
            'stop_table': {},
            'lnobj': None,
            'lntype': 1,
            'lnmode': info_data.get('lnmode', 1),
            'mode': 'DP' if is_dp else 'SP'
        }

        # Handle rank conversion if bmson judge_rank is specified in standard 100/etc scale
        # Typically bmson judge_rank of 100 is Normal (2) or Easy (3).
        # We check if rank is >= 5, in which case we map it:
        # e.g., standard bmson judge_rank: 100 is NORMAL (2).
        if isinstance(song_info['rank'], (int, float)) and song_info['rank'] >= 5:
            jr = song_info['rank']
            if jr >= 120:
                song_info['rank'] = 4  # VERY EASY
            elif jr >= 100:
                song_info['rank'] = 3  # EASY
            elif jr >= 80:
                song_info['rank'] = 2  # NORMAL
            elif jr >= 50:
                song_info['rank'] = 1  # HARD
            else:
                song_info['rank'] = 0  # VERY HARD

        wav_table = {}
        events = []

        # Mapping from bmson x-lane values to BMS channels
        # x is 1-based index: 1-7 for 1P keys, 8 for 1P scratch, 9-15 for 2P keys, 16 for 2P scratch
        X_TO_CHANNEL_NORMAL = {
            1: "11", 2: "12", 3: "13", 4: "14", 5: "15", 6: "18", 7: "19", 8: "16",
            9: "21", 10: "22", 11: "23", 12: "24", 13: "25", 14: "28", 15: "29", 16: "26"
        }
        X_TO_CHANNEL_LN = {
            1: "51", 2: "52", 3: "53", 4: "54", 5: "55", 6: "58", 7: "59", 8: "56",
            9: "61", 10: "62", 11: "63", 12: "64", 13: "65", 14: "68", 15: "69", 16: "66"
        }

        # 音源とイベントの抽出
        sound_channels = data.get('sound_channels', [])
        for channel in sound_channels:
            name = channel.get('name', '')
            if not name:
                continue
            # Store in wav_table: map the file name to itself
            # We normalize backslashes to forward slashes
            name_norm = name.replace('\\', '/')
            wav_table[name_norm] = name_norm

            notes = channel.get('notes', [])
            for note in notes:
                y = note.get('y', 0)
                l = note.get('l', 0)
                x = note.get('x', 0)
                c = note.get('c', False)
                beat = y / resolution
                sound_id_to_play = None if c else name_norm

                if x in X_TO_CHANNEL_NORMAL:
                    if l > 0:
                        # Long Note: generate start and end events
                        ch = X_TO_CHANNEL_LN[x]
                        end_beat = (y + l) / resolution
                        events.append({
                            'beat': beat,
                            'time': 0.0,
                            'sound_id': sound_id_to_play,
                            'channel': ch,
                            'ln_state': 'start'
                        })
                        events.append({
                            'beat': end_beat,
                            'time': 0.0,
                            'sound_id': sound_id_to_play,
                            'channel': ch,
                            'ln_state': 'end'
                        })
                    else:
                        ch = X_TO_CHANNEL_NORMAL[x]
                        events.append({
                            'beat': beat,
                            'time': 0.0,
                            'sound_id': sound_id_to_play,
                            'channel': ch
                        })
                else:
                    # BGM note (or key sound not played in any lane)
                    events.append({
                        'beat': beat,
                        'time': 0.0,
                        'sound_id': sound_id_to_play,
                        'channel': '01'
                    })

        # Add BPM changes
        for bpm_ev in data.get('bpm_events', []):
            y = bpm_ev.get('y', 0)
            bpm_val = bpm_ev.get('bpm')
            if bpm_val is not None:
                events.append({
                    'beat': y / resolution,
                    'time': 0.0,
                    'channel': '03',
                    'bpm': float(bpm_val)
                })

        # Add STOP events
        for stop_ev in data.get('stop_events', []):
            y = stop_ev.get('y', 0)
            duration = stop_ev.get('duration', 0)
            if duration > 0:
                # stop_val = 48.0 * duration / resolution
                stop_val = 48.0 * duration / resolution
                events.append({
                    'beat': y / resolution,
                    'time': 0.0,
                    'channel': '09',
                    'stop': float(stop_val)
                })

        # Add visual measure lines at the start of each measure (every 4 beats)
        max_beat = 0.0
        if events:
            max_beat = max(ev['beat'] for ev in events)
        for idx in range(int(max_beat / 4.0) + 2):
            m_start_beat = idx * 4.0
            events.append({
                'beat': m_start_beat,
                'time': 0.0,
                'channel': 'measure_line',
                'measure_idx': idx
            })

        # Sort events by beat and priority
        def get_event_priority(ev):
            ch = ev.get('channel', 'XX')
            if ch in ("03", "08"): return 0  # BPM change first
            if ch == "measure_line": return 1.5
            if ch == "09": return 3          # STOP last
            return 2                         # Notes / Sound channels

        events.sort(key=lambda x: (x['beat'], get_event_priority(x)))

        # Calculate time (seconds) sequentially
        current_sec = 0.0
        prev_beat = 0.0
        current_bpm = song_info['bpm']

        for ev in events:
            ev_beat = ev['beat']
            delta_beat = ev_beat - prev_beat
            if delta_beat > 0:
                current_sec += delta_beat * (60.0 / current_bpm)

            ev['time'] = current_sec

            if 'bpm' in ev:
                current_bpm = ev['bpm']
            if 'stop' in ev:
                stop_sec = stop_seconds(ev['stop'], current_bpm)
                current_sec += stop_sec

            prev_beat = ev_beat

        # Resolve LN partners
        ln_by_channel = {}
        for ev in events:
            if 'ln_state' in ev:
                ch = ev['channel']
                norm_ch = ch
                if ch.startswith('5'):
                    norm_ch = '1' + ch[1:]
                elif ch.startswith('6'):
                    norm_ch = '2' + ch[1:]
                ln_by_channel.setdefault(norm_ch, []).append(ev)

        for norm_ch, evs in ln_by_channel.items():
            evs.sort(key=lambda x: x['beat'])
            start_ev = None
            for ev in evs:
                if ev['ln_state'] == 'start':
                    start_ev = ev
                elif ev['ln_state'] == 'end' and start_ev is not None:
                    start_ev['ln_partner_beat'] = ev['beat']
                    start_ev['ln_partner_time'] = ev['time']
                    start_ev['ln_partner'] = ev
                    ev['ln_partner_beat'] = start_ev['beat']
                    ev['ln_partner_time'] = start_ev['time']
                    ev['ln_partner'] = start_ev
                    start_ev = None

        # bmson の total は相対値（デフォルト = 100）。
        # 未設定(None)のときのみデフォルト値 100.0 を補填する。
        # total = 0 は「ゲージ増加なし」を表す有効な値なので推定で上書きしない。
        # total < 0 は仕様上「絶対値を取る」とされているが、100.0 にフォールバックする。
        if not isinstance(song_info.get('total'), (int, float)):
            song_info['total'] = 100.0  # bmson spec default
        elif song_info['total'] < 0:
            song_info['total'] = abs(song_info['total'])



        # Construct BpmTimeline
        bpm_timeline_events = []
        stop_timeline_events = []
        for ev in events:
            if 'bpm' in ev:
                bpm_timeline_events.append((ev['beat'], ev['bpm']))
            if 'stop' in ev:
                stop_timeline_events.append((ev['beat'], ev['stop']))

        measures_multiplier = [1.0] * (int(max_beat / 4.0) + 100)
        timeline = BpmTimeline(
            initial_bpm=song_info['bpm'],
            bpm_events=bpm_timeline_events,
            stop_events=stop_timeline_events,
            measures_multiplier=measures_multiplier
        )

        # Channel to lane mapping
        channel_to_lane = CHANNEL_TO_LANE_LEFT.copy()
        ln_mapping = {}
        for ch, lane in channel_to_lane.items():
            if ch.startswith('1'):
                ln_mapping['5' + ch[1:]] = lane
            elif ch.startswith('2'):
                ln_mapping['6' + ch[1:]] = lane
        channel_to_lane.update(ln_mapping)

        return {
            'info': song_info,
            'wav_table': wav_table,
            'events': events,
            'base_path': os.path.dirname(file_path),
            'timeline': timeline,
            'channel_to_lane': channel_to_lane
        }

if __name__ == "__main__":
    print("Bmson Parser ready.")
