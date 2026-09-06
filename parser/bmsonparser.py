import json
import os
import re

from typing import Any, Optional
from constants import CHANNEL_TO_LANE_LEFT, CHANNEL_TO_LANE_RIGHT, get_channel_to_lane_map
from player.mine import is_mine_channel, decode_mine_damage, decode_mine_damage_numeric
from parser.mode_detector import detect_mode_from_bmson
from parser.util import get_event_priority, filter_duplicate_01_events, build_timeline, calculate_event_times, resolve_ln_partners

from config import load_bms_encoding

class BmsonParser:
    def __init__(self):
        pass

    def _add_measure_lines(
        self,
        events: list[dict[str, Any]],
        max_beat: float,
        lines_data: Optional[list[dict[str, Any]]] = None,
        resolution: int = 480
    ) -> None:
        """bmson用の小節線追加処理"""
        if lines_data is not None:
            # bmson specification: lines 配列が定義されている場合はその指定位置のみ使用
            for idx, line in enumerate(lines_data):
                if "y" in line:
                    events.append({
                        "beat": line["y"] / resolution,
                        "time": 0.0,
                        "channel": "measure_line",
                        "measure_idx": idx,
                    })
        else:
            # lines が省略されている場合は 4拍間隔で max_beat まで自動生成
            num_measures = int(max_beat / 4.0) + 2
            for idx in range(num_measures):
                m_start_beat = idx * 4.0
                if m_start_beat > max_beat:
                    break
                events.append({
                    "beat": m_start_beat,
                    "time": 0.0,
                    "channel": "measure_line",
                    "measure_idx": idx,
                })

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

        ext_is_pms = file_path.lower().endswith('.pms')
        raw_mode_hint = str(info_data.get('mode_hint', '')).lower().strip()

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

        detected_mode = detect_mode_from_bmson(raw_mode_hint, used_x, ext_is_pms)

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
        if detected_mode == '4K':
            X_TO_CHANNEL_NORMAL = {
                1: "11", 2: "12", 3: "14", 4: "15"
            }
            X_TO_CHANNEL_LN = {
                1: "51", 2: "52", 3: "54", 4: "55"
            }
        elif detected_mode == '6K':
            X_TO_CHANNEL_NORMAL = {
                1: "11", 2: "12", 3: "13", 4: "15", 5: "18", 6: "19"
            }
            X_TO_CHANNEL_LN = {
                1: "51", 2: "52", 3: "53", 4: "55", 5: "58", 6: "59"
            }
        elif detected_mode == '9K':
            X_TO_CHANNEL_NORMAL = {
                1: "11", 2: "12", 3: "13", 4: "14", 5: "15", 6: "22", 7: "23", 8: "24", 9: "25"
            }
            X_TO_CHANNEL_LN = {
                1: "51", 2: "52", 3: "53", 4: "54", 5: "55", 6: "62", 7: "63", 8: "64", 9: "65"
            }
        else:
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

        # Add visual measure lines at the start of each measure
        max_beat = max((ev['beat'] for ev in events), default=0.0)
        self._add_measure_lines(events, max_beat, data.get('lines'), resolution)

        # 01ch の重複除去
        events = filter_duplicate_01_events(events)
        # Sort events by beat and priority
        events.sort(key=lambda x: (x['beat'], get_event_priority(x)))

        # 時系列順（beat順）にBPM変化とSTOPコマンドを適用しながら累積経過時間を計算する。
        calculate_event_times(events, song_info['bpm'])

        # Resolve LN partners
        resolve_ln_partners(events)

        # bmson の total は相対値（デフォルト = 100）。
        # 未設定(None)のときのみデフォルト値 100.0 を補填する。
        # total = 0 は「ゲージ増加なし」を表す有効な値なので推定で上書きしない。
        # total < 0 は仕様上「絶対値を取る」とされているが、100.0 にフォールバックする。
        if not isinstance(song_info.get('total'), (int, float)):
            song_info['total'] = 100.0  # bmson spec default
        elif song_info['total'] < 0:
            song_info['total'] = abs(song_info['total'])

        measures_multiplier = [1.0] * (int(max_beat / 4.0) + 100)
        timeline = build_timeline(song_info, events, measures_multiplier)

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
