import json
import os
import re

class BmsParser:
    # ... (実装済み)
    def __init__(self):
        self.header_re = re.compile(r"^#(\w+)\s+(.+)")
        self.data_re = re.compile(r"^#(\d{3})(\d{2}):(\w+)")

    def parse(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"BMS file not found: {file_path}")

        info = {'title': '', 'artist': '', 'bpm': 120.0, 'rank': 3, 'total': None}
        wav_table = {}
        measures_multiplier = [1.0] * 1000
        raw_data = []

        # BMSは一般的にShift-JISまたはCP932が多い
        with open(file_path, 'r', encoding='shift-jis', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('#'): continue

                header_match = self.header_re.match(line)
                if header_match:
                    key, val = header_match.groups()
                    if key == "TITLE": info['title'] = val
                    elif key == "ARTIST": info['artist'] = val
                    elif key == "BPM":
                        try: info['bpm'] = float(val)
                        except: pass
                    elif key == "RANK":
                        try: info['rank'] = int(val)
                        except: pass
                    elif key == "TOTAL":
                        try:
                            total_val = int(val)
                            if total_val < 0:
                                raise ValueError
                            info['total'] = total_val
                        except:
                            # Default when invalid or negative
                            info['total'] = 0
                    elif key.startswith("WAV"):
                        id_36 = key[3:]
                        wav_table[id_36] = val
                    continue

                data_match = self.data_re.match(line)
                if data_match:
                    measure, channel, data_str = data_match.groups()
                    measure_idx = int(measure)
                    # Skip unnecessary BMS commands (e.g., BMP, BGA, background layers)
                    # NOTE: Channel "01" is BGM and must be kept.
                    # Future work: implement handling for STOP (channel "03") and BPM change (channel "08") commands.
                    skip_channels = {"03", "04", "05", "06", "07", "08", "09", "0A", "0B", "0C", "0D", "0E", "0F"}
                    if channel in skip_channels:
                        continue
                    raw_data.append((measure_idx, channel, data_str))

        measure_beats = [0.0] * 1000
        current_beat = 0.0
        for i in range(1000):
            measure_beats[i] = current_beat
            current_beat += 4.0 * measures_multiplier[i]

        events = []
        for measure, channel, data_str in raw_data:
            objects = [data_str[i:i+2] for i in range(0, len(data_str), 2)]
            n = len(objects)
            for i, obj in enumerate(objects):
                if obj == "00": continue
                beat = measure_beats[measure] + (i / n) * 4.0 * measures_multiplier[measure]
                events.append({
                    'beat': beat,
                    'time': beat, # Compatibility
                    'sound_id': obj,
                    'channel': channel
                })

        events.sort(key=lambda x: x['beat'])
        # If #TOTAL is missing or non‑positive, estimate a sensible default.
        # Use common BMS community formula: TOTAL = 7.605 * notes / (0.01 * notes + 6.5)
        # Clamp to a minimum of 260 (many players enforce this).
        if not isinstance(info.get('total'), (int, float)) or info['total'] <= 0:
            note_count = len(events)
            if note_count > 0:
                estimated = int(7.605 * note_count / (0.01 * note_count + 6.5))
                if estimated < 260:
                    estimated = 260
                info['total'] = estimated
            else:
                info['total'] = 0
        return {
            'info': info,
            'wav_table': wav_table,
            'events': events,
            'base_path': os.path.dirname(file_path)
        }

class BmsonParser:
    # ... (前回の実装を維持)
    def __init__(self):
        pass

    def parse(self, file_path):
        """bmsonファイルをパースして内部形式に変換する"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"bmson file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 抽出する基本情報
        info = data.get('info', {})
        song_info = {
            'title': info.get('title', 'Unknown'),
            'artist': info.get('artist', 'Unknown'),
            'bpm': info.get('init_bpm', 120.0),
        }

        # 音源とイベントの抽出
        events = []
        sound_channels = data.get('sound_channels', [])
        
        for channel in sound_channels:
            name = channel.get('name', '')
            notes = channel.get('notes', [])
            for note in notes:
                events.append({
                    'time': note.get('y', 0),    # y座標（pulseまたは拍数ベース）
                    'sound_id': name,
                    'type': 'sound'
                })

        # 時間順にソート
        events.sort(key=lambda x: x['time'])

        return {
            'info': song_info,
            'events': events
        }

if __name__ == "__main__":
    print("Bmson Parser ready.")
