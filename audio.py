import miniaudio
import os

import threading
import array

from config import load_audio_config

class AudioEngine:
    def __init__(self):
        self.sounds = {} # {sound_id: DecodedSoundFile}
        self.active_sounds = [] # [{"samples": array, "position": int}]
        self.lock = threading.Lock()

        # バックグラウンドロード用の状態管理
        self._loading_thread = None
        self._loaded_count = 0
        self._total_count = 0

        # settings.toml からオーディオ設定を読み込む
        audio_cfg = load_audio_config()
        self.sample_rate = audio_cfg['sample_rate']
        self.nchannels   = audio_cfg['nchannels']

        # PlaybackDeviceの初期化 – バッファサイズは milliseconds で指定
        # 3msは攻めすぎてノイズ多いので10msに
        self.device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=self.nchannels,
            sample_rate=self.sample_rate,
            buffersize_msec=10,
        )
        
        # ジェネレータの作成と起動
        self.generator = self._mix_generator()
        next(self.generator) # 最初のyieldまで進める
        
        # 再生開始
        self.device.start(self.generator)

    @property
    def is_loading(self):
        """バックグラウンドでWAVファイルをロード中かどうか"""
        return self._loading_thread is not None and self._loading_thread.is_alive()

    @property
    def loading_progress(self):
        """(ロード済み件数, 全件数) のタプルを返す"""
        return (self._loaded_count, self._total_count)

    def _mix_generator(self):
        nchannels = self.nchannels
        # Initial yield to receive the first frame count request
        required_frames = yield b""
        while True:
            required_samples = required_frames * nchannels
            # Initialize output buffer as a list of ints for safe mixing
            output_list = [0] * required_samples
            finished_sounds = []

            # Mix active sounds safely
            with self.lock:
                sounds_to_process = list(self.active_sounds)
            for sound in sounds_to_process:
                pos = sound["position"]
                src = sound["samples"]
                src_len = len(src)
                remaining = src_len - pos
                to_copy = min(required_samples, remaining)
                
                # スライス抽出して加算ループを最適化
                chunk = src[pos : pos + to_copy]
                for i, val in enumerate(chunk):
                    output_list[i] += val

                sound["position"] += to_copy
                if sound["position"] >= src_len:
                    finished_sounds.append(sound)

            # Remove finished sounds (一括フィルタリングで O(n) 化)
            if finished_sounds:
                finished_set = set(id(snd) for snd in finished_sounds)
                with self.lock:
                    self.active_sounds = [snd for snd in self.active_sounds if id(snd) not in finished_set]

            # Clip and convert to signed 16‑bit array
            # リスト内包表記と三項演算子で高速化
            clipped = [
                32767 if val > 32767 else (-32768 if val < -32768 else val)
                for val in output_list
            ]
            output = array.array('h', clipped)

            # Yield mixed audio and receive next frame request
            required_frames = yield output.tobytes()

    def load_sound(self, sound_id, file_path):
        """音源ファイルをデコードしてメモリにロードする"""
        if not os.path.exists(file_path):
            return False
        try:
            # PlaybackDevice と同一のフォーマット（SIGNED16 + 設定チャンネル数 + 設定レート）にデコードする
            sound = miniaudio.decode_file(
                file_path,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=self.nchannels,
                sample_rate=self.sample_rate
            )
            self.sounds[sound_id] = sound
            return True
        except Exception as e:
            # デバッグ用にログを出力
            print(f"Error loading {file_path}: {e}")
            return False

    def load_wav_table(self, wav_table, base_path):
        """BMSのWAVテーブルに基づいて音源を一括ロードする（同期版）"""
        for sound_id, file_name in wav_table.items():
            file_name = file_name.replace('\\', '/')
            name, ext = os.path.splitext(file_name)
            path_no_ext = os.path.join(base_path, name)
            
            loaded = False
            for e in ['.wav', '.ogg', '.WAV', '.OGG', '.flac', '.FLAC', '.mp3', '.MP3', ext]:
                full_path = path_no_ext + e
                if os.path.exists(full_path):
                    if self.load_sound(sound_id, full_path):
                        loaded = True
                        break
            if not loaded:
                print(f"Warning: Failed to load {sound_id} ({file_name})")

    def load_wav_table_async(self, wav_table, base_path, on_done=None):
        """BMSのWAVテーブルに基づいて音源をバックグラウンドスレッドでロードする。

        ロード完了後に on_done コールバック（引数なし）が呼ばれる（省略可）。
        ロード状態は is_loading / loading_progress プロパティで確認できる。
        """
        self._loaded_count = 0
        self._total_count = len(wav_table)

        def _worker():
            for sound_id, file_name in wav_table.items():
                file_name = file_name.replace('\\', '/')
                name, ext = os.path.splitext(file_name)
                path_no_ext = os.path.join(base_path, name)

                for e in ['.wav', '.ogg', '.WAV', '.OGG', '.flac', '.FLAC', '.mp3', '.MP3', ext]:
                    full_path = path_no_ext + e
                    if os.path.exists(full_path):
                        self.load_sound(sound_id, full_path)
                        break
                self._loaded_count += 1

            if on_done is not None:
                on_done()

        self._loading_thread = threading.Thread(target=_worker, daemon=True)
        self._loading_thread.start()

    def play(self, sound_id, limit=1):
        """ロード済みの音を再生する"""
        if sound_id in self.sounds:
            sound = self.sounds[sound_id]
            # 新しい再生インスタンスを作成して追加
            with self.lock:
                # すでに再生中の同じ sound_id の音を検索
                matching = [snd for snd in self.active_sounds if snd.get("sound_id") == sound_id]
                # 制限数を満たすために、古い音を削除 (一括フィルタリング)
                if matching:
                    if limit <= 1:
                        to_remove = set(id(snd) for snd in matching)
                    else:
                        excess = len(matching) - limit + 1
                        if excess > 0:
                            to_remove = set(id(snd) for snd in matching[:excess])
                        else:
                            to_remove = None

                    if to_remove:
                        self.active_sounds = [snd for snd in self.active_sounds if id(snd) not in to_remove]

                self.active_sounds.append({
                    "sound_id": sound_id,
                    "samples": sound.samples,
                    "position": 0
                })

        else:
            pass # サイレント

    def stop_all(self):
        """すべての音を停止"""
        with self.lock:
            self.active_sounds.clear()

    def close(self):
        """デバイスを閉じる"""
        self.device.close()

if __name__ == "__main__":
    import time
    print("Testing Audio Engine with manual mixer...")
    ae = AudioEngine()
    print(f"Initialized: sample_rate={ae.sample_rate}, nchannels={ae.nchannels}")
    ae.close()
