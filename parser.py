import json
import os
import re

from typing import Dict, List, Tuple, Any
#import logging
from constants import CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT, get_channel_to_lane_map
from timing import BpmTimeline, stop_seconds, estimated_total
from player.mine import is_mine_channel, decode_mine_damage, decode_mine_damage_numeric

from config import load_bms_encoding

class BmsParser:
    """Parse BMS files into a structured chart representation.
    The parser extracts header information, wav table, measure multipliers,
    and builds a list of timed events.
    """
    def __init__(self):
        self.header_re = re.compile(r"^#(\w+)\s+(.+)")
        self.data_re = re.compile(r"^#(\d{3})([0-9a-zA-Z]{2}):(.+)")
        # 制御フロー命令を識別する正規表現
        self._re_random   = re.compile(r"^#(?:RANDOM|RONDAM)\s+(\d+)", re.IGNORECASE)
        self._re_if       = re.compile(r"^#IF\s+(\d+)", re.IGNORECASE)
        self._re_elseif   = re.compile(r"^#ELSEIF\s+(\d+)", re.IGNORECASE)
        self._re_else     = re.compile(r"^#ELSE\b", re.IGNORECASE)
        self._re_endif    = re.compile(r"^#(?:ENDIF|END)\b", re.IGNORECASE)
        self._re_endrandom= re.compile(r"^#ENDRANDOM\b", re.IGNORECASE)

    # ------------------------------------------------------------------
    # #RANDOM / #IF 系プリプロセッサ
    # ------------------------------------------------------------------
    def _preprocess_random(self, lines: list) -> list:
        """#RANDOM / #IF 制御フローを処理し、有効な行のみを返す。

        スタックを使ってネストに対応する。各 #RANDOM ブロックは:
          rand_val  : 生成された乱数
          if_state  : 現在の #IF ブロックの状態
                      'search'  … まだ一致ブロックを探している
                      'active'  … 一致して現在実行中
                      'done'    … すでに一致済み（#ELSEIF/#ELSE をスキップ）
                      'outer_skip' … 外側のブロックが非アクティブなので丸ごとスキップ
          in_if     : #IF〜#ENDIF ブロックの中にいるか
        """
        import random as _random

        # スタックの各要素: {'rand_val': int, 'if_state': str, 'in_if': bool}
        # トップレベルは「常に active」を表す番兵エントリ
        stack = [{'rand_val': None, 'if_state': 'active', 'in_if': False}]

        result = []

        def _is_active():
            """現在の行を出力すべきか。スタック全段が active なら True。"""
            for frame in stack:
                state = frame['if_state']
                if state in ('search', 'done', 'outer_skip'):
                    return False
            return True

        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()

            # --- #RANDOM / #RONDAM ---
            m = self._re_random.match(stripped)
            if m:
                n = max(1, int(m.group(1)))
                rand_val = _random.randint(1, n)
                # 外側が非アクティブなら丸ごとスキップ状態でネスト
                outer_active = _is_active()
                state = 'search' if outer_active else 'outer_skip'
                stack.append({'rand_val': rand_val, 'if_state': state, 'in_if': False})
                # 制御命令自体は出力しない
                continue

            # --- #ENDRANDOM ---
            if self._re_endrandom.match(stripped):
                if len(stack) > 1:  # 番兵は残す<-番兵って何？
                    stack.pop()
                continue

            # --- #IF ---
            m = self._re_if.match(stripped)
            if m:
                n = int(m.group(1))
                frame = stack[-1]
                frame['in_if'] = True
                if frame['if_state'] == 'search':
                    if frame['rand_val'] == n:
                        frame['if_state'] = 'active'
                    # else: 引き続き search（次の #IF / #ELSEIF を待つ）
                elif frame['if_state'] == 'active':
                    # すでに一致済みの別 #IF ブロック → done に遷移
                    frame['if_state'] = 'done'
                # outer_skip / done のときは何もしない
                continue

            # --- #ELSEIF ---
            m = self._re_elseif.match(stripped)
            if m:
                n = int(m.group(1))
                frame = stack[-1]
                if frame['if_state'] == 'active':
                    # 現在 active なブロックが終わり → done に
                    frame['if_state'] = 'done'
                elif frame['if_state'] == 'search':
                    if frame['rand_val'] == n:
                        frame['if_state'] = 'active'
                # done / outer_skip のときは何もしない
                continue

            # --- #ELSE ---
            if self._re_else.match(stripped):
                frame = stack[-1]
                if frame['if_state'] == 'active':
                    frame['if_state'] = 'done'
                elif frame['if_state'] == 'search':
                    frame['if_state'] = 'active'
                # done / outer_skip のときは何もしない
                continue

            # --- #ENDIF / #END ---
            if self._re_endif.match(stripped):
                frame = stack[-1]
                # #RANDOM ブロック内で #IF が見つかっていたら search 状態に戻す
                if frame['if_state'] != 'outer_skip':
                    frame['if_state'] = 'search'
                frame['in_if'] = False
                continue

            # --- 空行・コメント行のスキップ ---
            if not stripped or stripped.startswith('//'):
                if _is_active():
                    result.append(line)
                continue

            # --- 通常命令行 ---
            # #ENDRANDOM 省略対応:
            # #IF〜#ENDIF の外側(in_if == False)で、次の #IF / #ELSE / #ELSEIF / #ENDIF 等ではなく
            # 通常のデータ行/ヘッダー行が来た場合、#ENDRANDOM が省略されたとみなして pop する。
            while len(stack) > 1 and not stack[-1]['in_if'] and \
                    stack[-1]['if_state'] in ('search', 'done', 'outer_skip'):
                stack.pop()

            if _is_active():
                result.append(line)

        return result

    def _parse_header(self, line: str, info: dict, wav_table: dict, base: int) -> None:
        """Parse a header line and update info or wav_table.
        Args:
            line: The raw line string starting with '#'.
            info: Dictionary accumulating song metadata.
            wav_table: Dictionary mapping wav IDs to file paths.
            base: Active radix for parsing IDs.
        """
        header_match = self.header_re.match(line)
        if not header_match:
            return
        key, val = header_match.groups()
        key_upper = key.upper()

        def clean_id(raw_id: str) -> str:
            if base == 62:
                return raw_id
            return raw_id.upper()

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
            id_36 = clean_id(key[3:])
            try:
                info['bpm_table'][id_36] = float(val)
            except Exception:
                pass
        elif key_upper.startswith("STOP") and len(key_upper) > 4:
            id_36 = clean_id(key[4:])
            try:
                info['stop_table'][id_36] = float(val)
            except Exception:
                pass
        elif key_upper.startswith("SCROLL") and len(key_upper) > 6:
            id_36 = clean_id(key[6:])
            try:
                info['scroll_table'][id_36] = float(val)
            except Exception:
                pass
        elif key_upper == "RANK":
            try:
                info['rank'] = int(val)
            except Exception:
                pass
        elif key_upper == "LNOBJ":
            info['lnobj'] = clean_id(val)
        elif key_upper == "LNTYPE":
            try:
                info['lntype'] = int(val)
            except Exception:
                pass
        elif key_upper.startswith("LNMODE"):
            try:
                info['lnmode'] = int(val)
            except Exception:
                pass
        elif key_upper.startswith("WAV"):
            wav_id = clean_id(key[3:])
            wav_table[wav_id] = val
        elif key_upper == "BASE":
            try:
                info['base'] = int(val)
            except Exception:
                pass

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

    def parse(self, file_path: str, encoding: str = None) -> dict:
        """Parse a BMS file and return a structured chart dict.
        The method builds header info, wav table, measures multiplier, raw data,
        then computes beat timings and converts them to absolute seconds.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"BMS file not found: {file_path}")

        if encoding is None:
            encoding = load_bms_encoding()

        info = {
            'title': '',
            'artist': '',
            'bpm': 130.0,
            'rank': 3,
            'total': None,
            'bpm_table': {},
            'stop_table': {},
            'scroll_table': {},
            'lnobj': None,
            'lntype': 1,
            'lnmode': 1,
            'base': 36
        }
        wav_table = {}
        measures_multiplier = [1.0] * 1000
        raw_data = []

        base = 36
        # Pre-scan for #BASE to know if we need case sensitivity
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('#'): continue
                m = re.match(r"^#BASE\s+(\d+)", line, re.IGNORECASE)
                if m:
                    try:
                        base = int(m.group(1))
                        info['base'] = base
                    except:
                        pass
                    break

        def clean_id(raw_id: str) -> str:
            if base == 62:
                return raw_id
            return raw_id.upper()

        # BMSは一般的にShift-JISまたはCP932が多い
        # #RANDOM / #IF 制御フローをプリプロセスして有効行のみに絞り込む
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            all_lines = f.readlines()
        preprocessed_lines = self._preprocess_random(all_lines)

        for line in preprocessed_lines:
            line = line.strip()
            if not line.startswith('#'): continue

            # Determine if line is a header or data and delegate parsing
            header_match = self.header_re.match(line)
            if header_match:
                # Use helper to parse header line
                self._parse_header(line, info, wav_table, base)
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
                    # 拡張BPMテーブル（36/62進数定義）から参照
                    ref_key = clean_id(obj)
                    if ref_key in info['bpm_table']:
                        bpm_val = info['bpm_table'][ref_key]
                elif channel == "09":
                    # STOPテーブルから参照
                    ref_key = clean_id(obj)
                    if ref_key in info['stop_table']:
                        stop_val = info['stop_table'][ref_key]
                elif channel.upper() == "SC":
                    # SCROLLテーブルから参照
                    ref_key = clean_id(obj)
                    if ref_key in info['scroll_table']:
                        scroll_val = info['scroll_table'][ref_key]
                        event_data = {
                            'beat': beat,
                            'time': 0.0,
                            'channel': 'SC',
                            'scroll': scroll_val
                        }
                        events.append(event_data)
                        continue

                event_data = {
                    'beat': beat,
                    'time': 0.0, # あとで秒数に変換して上書きする
                    'sound_id': clean_id(obj),
                    'channel': channel
                }
                if bpm_val is not None:
                    event_data['bpm'] = bpm_val
                if stop_val is not None:
                    event_data['stop'] = stop_val

                # 地雷チャンネル (D1-D9, E1-E9) の場合は is_mine フラグと mine_damage を付与
                # obj はダメージ値 (base-36) であり、WAVテーブルキーではないため sound_id を None にする
                if is_mine_channel(channel):
                    event_data['is_mine'] = True
                    event_data['mine_damage'] = decode_mine_damage(obj)
                    event_data['sound_id'] = None

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
                                'sound_id': clean_id(obj),
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
                    if ev['sound_id'] == info['lnobj']:
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
            if ch in ("03", "08") or ch == "SC": return 0  # BPM / SCROLL change first
            if ch == "measure_line": return 1.5
            if ch == "09": return 3          # STOP last (after note channels at 2)
            return 2                         # Notes / Sound channels last

        # 01ch の重複除去
        # 除去条件①: 11-69ch に同一 (beat, sound_id) があれば 01ch を除去
        # 除去条件②: 01ch 同士で同一 (beat, sound_id) が重複すれば後発を除去
        # TODO: BmsonParser にも同一ブロックが存在するため、後でヘルパー関数に切り出してリファクタリングすること
        _playable_ch = {
            "11","12","13","14","15","16","17","18","19",
            "21","22","23","24","25","26","27","28","29",
            "51","52","53","54","55","56","57","58","59",
            "61","62","63","64","65","66","67","68","69"
        }
        _playable_keys = {
            (ev['beat'], ev['sound_id'])
            for ev in events
            if ev.get('channel') in _playable_ch and ev.get('sound_id') is not None
        }
        _seen_01: set = set()
        _filtered: list = []
        for ev in events:
            if ev.get('channel') == '01':
                key = (ev['beat'], ev.get('sound_id'))
                if key in _playable_keys or key in _seen_01:
                    continue
                _seen_01.add(key)
            _filtered.append(ev)
        events = _filtered

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
        scroll_timeline_events = []
        for ev in events:
            if 'bpm' in ev:
                bpm_timeline_events.append((ev['beat'], ev['bpm']))
            if 'stop' in ev:
                stop_timeline_events.append((ev['beat'], ev['stop']))
            if 'scroll' in ev:
                scroll_timeline_events.append((ev['beat'], ev['scroll']))
                
        timeline = BpmTimeline(
            initial_bpm=info['bpm'],
            bpm_events=bpm_timeline_events,
            stop_events=stop_timeline_events,
            measures_multiplier=measures_multiplier,
            scroll_events=scroll_timeline_events
        )

        # 全ノーツチャンネルの集計によるキーモード自動決定
        used_channels = {ch for _, ch, _ in raw_data}
        has_1P_7k = bool(used_channels & {"18", "19", "58", "59", "D8", "D9"})
        has_2P_any = bool(used_channels & {
            "21", "22", "23", "24", "25", "26", "27", "28", "29",
            "61", "62", "63", "64", "65", "66", "67", "68", "69",
            "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9"
        })
        has_2P_7k = bool(used_channels & {"28", "29", "68", "69", "E8", "E9"})

        if has_2P_any:
            detected_mode = '14K' if (has_1P_7k or has_2P_7k) else '10K'
        else:
            detected_mode = '7K' if has_1P_7k else '5K'

        info['mode'] = detected_mode
        info['player_mode'] = 'DP' if detected_mode in ('10K', '14K') else 'SP'

        channel_to_lane = get_channel_to_lane_map(detected_mode, 'left')
        chart_channel_to_lane = channel_to_lane

        return {
            'info': info,
            'wav_table': wav_table,
            'polyphony_table': {},
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

        # Determine mode by aggregating all used x-coordinates across sound_channels and mine_channels
        used_x = set()
        for channel in data.get('sound_channels', []):
            for note in channel.get('notes', []):
                x = note.get('x')
                if x is not None:
                    used_x.add(x)
        for mine_ch in data.get('mine_channels', []):
            for note in mine_ch.get('notes', []):
                x = note.get('x')
                if x is not None:
                    used_x.add(x)

        has_1P_7k = bool(used_x & {6, 7})
        has_2P_any = bool(used_x & set(range(9, 17)))
        has_2P_7k = bool(used_x & {14, 15})

        if has_2P_any:
            detected_mode = '14K' if (has_1P_7k or has_2P_7k) else '10K'
        else:
            detected_mode = '7K' if has_1P_7k else '5K'

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
            'mode': detected_mode,
            'player_mode': 'DP' if detected_mode in ('10K', '14K') else 'SP'
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

        polyphony_table = {}

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
            
            # polyphony があればパースし、なければデフォルト 1
            polyphony = channel.get('polyphony', 1)
            polyphony_table[name_norm] = int(polyphony)

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

        # mine_channels の抽出 (bmson 独自拡張: beatoraja 等で対応)
        mine_channels_data = data.get('mine_channels', [])
        for mine_ch in mine_channels_data:
            name = mine_ch.get('name', '')
            # 爆発音ファイルがあれば wav_table に登録する
            explosion_sound = None
            if name:
                name_norm = name.replace('\\', '/')
                wav_table[name_norm] = name_norm
                explosion_sound = name_norm

            notes = mine_ch.get('notes', [])
            for note in notes:
                y = note.get('y', 0)
                x = note.get('x', 0)
                damage = note.get('damage', 0)
                beat = y / resolution

                if x in X_TO_CHANNEL_NORMAL:
                    ch = X_TO_CHANNEL_NORMAL[x]  # 通常チャンネルでレーンを引く
                    events.append({
                        'beat': beat,
                        'time': 0.0,
                        'sound_id': explosion_sound,  # 爆発音 (None でも可)
                        'channel': ch,
                        'is_mine': True,
                        'mine_damage': decode_mine_damage_numeric(damage),
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

        # Add SCROLL events
        for scroll_ev in data.get('scroll_events', []):
            y = scroll_ev.get('y', 0)
            rate_val = scroll_ev.get('rate', 1.0)
            try:
                rate_val = float(rate_val)
            except (ValueError, TypeError):
                rate_val = 1.0
            rate_val = max(0.0, rate_val)
            events.append({
                'beat': y / resolution,
                'time': 0.0,
                'channel': 'SC',
                'scroll': rate_val
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
            if ch in ("03", "08") or ch == "SC": return 0  # BPM / SCROLL change first
            if ch == "measure_line": return 1.5
            if ch == "09": return 3          # STOP last
            return 2                         # Notes / Sound channels

        # 01ch の重複除去
        # 除去条件①: 11-69ch に同一 (beat, sound_id) があれば 01ch を除去
        # 除去条件②: 01ch 同士で同一 (beat, sound_id) が重複すれば後発を除去
        # TODO: BmsParser にも同一ブロックが存在するため、後でヘルパー関数に切り出してリファクタリングすること
        _playable_ch = {
            "11","12","13","14","15","16","17","18","19",
            "21","22","23","24","25","26","27","28","29",
            "51","52","53","54","55","56","57","58","59",
            "61","62","63","64","65","66","67","68","69"
        }
        _playable_keys = {
            (ev['beat'], ev['sound_id'])
            for ev in events
            if ev.get('channel') in _playable_ch and ev.get('sound_id') is not None
        }
        _seen_01: set = set()
        _filtered: list = []
        for ev in events:
            if ev.get('channel') == '01':
                key = (ev['beat'], ev.get('sound_id'))
                if key in _playable_keys or key in _seen_01:
                    continue
                _seen_01.add(key)
            _filtered.append(ev)
        events = _filtered

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
        scroll_timeline_events = []
        for ev in events:
            if 'bpm' in ev:
                bpm_timeline_events.append((ev['beat'], ev['bpm']))
            if 'stop' in ev:
                stop_timeline_events.append((ev['beat'], ev['stop']))
            if 'scroll' in ev:
                scroll_timeline_events.append((ev['beat'], ev['scroll']))

        measures_multiplier = [1.0] * (int(max_beat / 4.0) + 100)
        timeline = BpmTimeline(
            initial_bpm=song_info['bpm'],
            bpm_events=bpm_timeline_events,
            stop_events=stop_timeline_events,
            measures_multiplier=measures_multiplier,
            scroll_events=scroll_timeline_events
        )

        # Channel to lane mapping
        channel_to_lane = get_channel_to_lane_map(song_info['mode'], 'left')

        return {
            'info': song_info,
            'wav_table': wav_table,
            'polyphony_table': polyphony_table,
            'events': events,
            'base_path': os.path.dirname(file_path),
            'timeline': timeline,
            'channel_to_lane': channel_to_lane
        }

if __name__ == "__main__":
    print("Bmson Parser ready.")
