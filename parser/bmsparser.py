import json
import os
import re

from typing import Any
from constants import CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT, get_channel_to_lane_map
from timing import estimated_total
from player.mine import is_mine_channel, decode_mine_damage, decode_mine_damage_numeric
from parser.mode_detector import detect_mode_from_bms
from parser.util import get_event_priority, filter_duplicate_01_events, build_timeline, calculate_event_times, resolve_ln_partners

from config import load_bms_encoding

class BmsParser:
    """Parse BMS files into a structured chart representation.
    The parser extracts header information, wav table, measure multipliers,
    and builds a list of timed events.
    """
    def __init__(self):
        self.header_re = re.compile(r"^#(\w+)(?:\s+(.+))?")
        self.data_re = re.compile(r"^#(\d{3})([0-9a-zA-Z]{2}):(.+)")
        # 制御フロー命令を識別する正規表現
        self._re_random   = re.compile(r"^#(?:RANDOM|RONDAM)\s+(\d+)", re.IGNORECASE)
        self._re_if       = re.compile(r"^#IF\s+(\d+)", re.IGNORECASE)
        self._re_elseif   = re.compile(r"^#ELSEIF\s+(\d+)", re.IGNORECASE)
        self._re_else     = re.compile(r"^#ELSE\b", re.IGNORECASE)
        self._re_endif    = re.compile(r"^#(?:ENDIF|END)\b", re.IGNORECASE)
        self._re_endrandom= re.compile(r"^#ENDRANDOM\b", re.IGNORECASE)

    def _add_measure_lines(self, events: list[dict[str, Any]], measure_beats: list[float]) -> None:
        """BMS用の小節線追加処理"""
        if not events:
            return
        max_beat = max(ev["beat"] for ev in events)
        for idx, m_start_beat in enumerate(measure_beats):
            if m_start_beat > max_beat:
                break
            events.append({
                "beat": m_start_beat,
                "time": 0.0,
                "channel": "measure_line",
                "measure_idx": idx,
            })

    # ------------------------------------------------------------------
    # #RANDOM / #IF 系プリプロセッサ
    # ------------------------------------------------------------------
    def _preprocess_random(self, lines: list) -> list:
        """#RANDOM / #IF 制御フローを処理し、有効な行のみを返す。
        複数の #RANDOM 命令が直列に配置されている場合やネストにも対応。

        スタックを使ってネスト・直列に対応する。各 #RANDOM ブロックは:
          rand_val  : 生成された乱数
          if_state  : 現在の #IF ブロックの状態
                      'search'     … まだ一致ブロックを探している
                      'active'     … 一致して現在実行中
                      'done'       … すでに一致済み（#ELSEIF/#ELSE をスキップ）
                      'block_end'  … #ENDIF等で1つのIFブロックが終了した状態
                      'outer_skip' … 外側のブロックが非アクティブなので丸ごとスキップ
          in_if     : #IF〜#ENDIF ブロックの中にいるか
        """
        import random as _random

        # スタックの各要素: {'rand_val': int, 'if_state': str, 'in_if': bool}
        # トップレベル（index 0）は常に active
        stack = [{'rand_val': None, 'if_state': 'active', 'in_if': False}]
        result = []

        def _is_active():
            for frame in stack:
                if frame['if_state'] in ('search', 'done', 'outer_skip'):
                    return False
            return True

        for line in lines:
            stripped = line.strip()

            # --- 空行・コメント行のスキップ ---
            if not stripped or stripped.startswith('//'):
                if _is_active():
                    result.append(line)
                continue

            # --- #RANDOM / #RONDAM ---
            m = self._re_random.match(stripped)
            if m:
                # すでに前の #RANDOM ブロックの #IF〜#ENDIF の外側にいるなら
                # 前の #RANDOM ブロックを終了(pop)させてから新しい #RANDOM を開始する
                while len(stack) > 1 and not stack[-1]['in_if']:
                    stack.pop()

                n = max(1, int(m.group(1)))
                rand_val = _random.randint(1, n)
                outer_active = _is_active()
                state = 'search' if outer_active else 'outer_skip'
                stack.append({'rand_val': rand_val, 'if_state': state, 'in_if': False})
                continue

            # --- #ENDRANDOM ---
            if self._re_endrandom.match(stripped):
                if len(stack) > 1:
                    stack.pop()
                continue

            # --- #IF ---
            m = self._re_if.match(stripped)
            if m:
                n = int(m.group(1))
                frame = stack[-1]
                frame['in_if'] = True
                if frame['if_state'] in ('search', 'block_end'):
                    if frame['rand_val'] == n:
                        frame['if_state'] = 'active'
                    else:
                        frame['if_state'] = 'search'
                elif frame['if_state'] == 'active':
                    # #ENDIF なしで次の #IF が来た場合
                    if frame['rand_val'] == n:
                        frame['if_state'] = 'active'
                    else:
                        frame['if_state'] = 'done'
                continue

            # --- #ELSEIF ---
            m = self._re_elseif.match(stripped)
            if m:
                n = int(m.group(1))
                frame = stack[-1]
                if frame['if_state'] == 'active':
                    frame['if_state'] = 'done'
                elif frame['if_state'] in ('search', 'block_end'):
                    if frame['rand_val'] == n:
                        frame['if_state'] = 'active'
                continue

            # --- #ELSE ---
            if self._re_else.match(stripped):
                frame = stack[-1]
                if frame['if_state'] == 'active':
                    frame['if_state'] = 'done'
                elif frame['if_state'] in ('search', 'block_end'):
                    frame['if_state'] = 'active'
                continue

            # --- #ENDIF / #END ---
            if self._re_endif.match(stripped):
                frame = stack[-1]
                if frame['if_state'] != 'outer_skip':
                    # ブロック終了時は 'block_end' に更新 ('search' に戻さない)
                    frame['if_state'] = 'block_end'
                frame['in_if'] = False
                continue

            # --- 通常のデータ行 / ヘッダー行 ---
            # #ENDRANDOM 省略対応:
            # #IF ブロックの外側で通常データ行が来た場合、現在の #RANDOM を終了(pop)する
            if len(stack) > 1 and not stack[-1]['in_if'] and stack[-1]['if_state'] == 'block_end':
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
        elif key_upper == "4K":
            info['forced_mode'] = '4K'
        elif key_upper == "6K":
            info['forced_mode'] = '6K'
        elif key_upper == "MODE":
            val_str = (val or '').strip()
            if val_str == "4":
                info['forced_mode'] = '4K'
            elif val_str == "6":
                info['forced_mode'] = '6K'
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

            # If it's a data line (#00111:01020304 etc.), parse data line first
            data_match = self.data_re.match(line)
            if data_match:
                self._parse_data(line, measures_multiplier, raw_data)
                continue

            # Otherwise, check if line is a header line (#TITLE, #BPM, #4K, #6K etc.)
            header_match = self.header_re.match(line)
            if header_match:
                self._parse_header(line, info, wav_table, base)
                continue

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
        self._add_measure_lines(events, measure_beats)

        # 01ch の重複除去
        events = filter_duplicate_01_events(events)
        # Sort events by beat and priority
        events.sort(key=lambda x: (x['beat'], get_event_priority(x)))
        
        # 時系列順（beat順）にBPM変化とSTOPコマンドを適用しながら累積経過時間を計算する。
        calculate_event_times(events, info['bpm'])

        # Resolve LN partners
        resolve_ln_partners(events)

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
        timeline = build_timeline(info, events, measures_multiplier)

        # 全ノーツチャンネルの集計によるキーモード自動決定
        info['ext_is_pms'] = file_path.lower().endswith('.pms')
        used_channels = {ch for _, ch, _ in raw_data}

        detected_mode = detect_mode_from_bms(info, used_channels)

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
