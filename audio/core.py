import miniaudio
import os

import threading
import array

try:
    import numpy as np
    _USE_NUMPY = True
except ImportError:
    _USE_NUMPY = False

from helpers.options import load_options
from audio.resolve_audio_path import resolve_audio_path

# 音声ファイルサイズの上限（デフォルト 100MB）
_MAX_AUDIO_FILE_SIZE = 100 * 1024 * 1024

# 音声ファイル再生時間の上限（秒）
# RIFF WAV 16bit 44100Hz stereo で ~10分=100MB を目安に、余裕を持って 30 分を上限とする
_MAX_AUDIO_DURATION_SEC = 30 * 60  # 1800 秒

class AudioEngine:
    def __init__(self):
        self.sounds = {} # {sound_id: DecodedSoundFile}
        self.active_sounds = [] # [{"samples": array, "position": int}]
        self.lock = threading.Lock()

        # バックグラウンドロード用の状態管理
        self._loading_thread = None
        self._loaded_count = 0
        self._total_count = 0

        # 音声読み込みエラーのログ（curses 上で表示するために print の代わりに蓄積）
        self.load_errors = []

        # settings.toml からオーディオ設定を読み込む
        opts = load_options()
        self.sample_rate = opts.sample_rate
        self.nchannels   = opts.nchannels
        self.max_memory_bytes = getattr(opts, 'max_memory_mb', 1024) * 1024 * 1024
        self.total_pcm_bytes = 0
        self._file_cache = {}  # {canonical_file_path: DecodedSoundFile}

        # PlaybackDeviceの初期化 – バッファサイズは milliseconds で指定
        # 3msは攻めすぎてノイズ多いので10msに
        self.device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=self.nchannels,
            sample_rate=self.sample_rate,
            buffersize_msec=10,
        )
        
        # 再生済みフレーム数（オーディオマスタークロック用）
        self.played_frames = 0

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

        if _USE_NUMPY:
            # --- numpy パス ---
            while True:
                required_samples = required_frames * nchannels
                output_buf = np.zeros(required_samples, dtype=np.int32)
                finished_sounds = []

                with self.lock:
                    sounds_to_process = list(self.active_sounds)
                for sound in sounds_to_process:
                    pos = sound["position"]
                    src = sound["samples"]  # array.array('h')
                    src_len = len(src)
                    remaining = src_len - pos
                    to_copy = min(required_samples, remaining)

                    # array.array のスライスを numpy 配列に変換して加算
                    chunk = np.frombuffer(
                        memoryview(src)[pos : pos + to_copy],
                        dtype=np.int16
                    ).astype(np.int32)
                    output_buf[:to_copy] += chunk

                    sound["position"] += to_copy
                    if sound["position"] >= src_len:
                        finished_sounds.append(sound)

                # Remove finished sounds (一括フィルタリングで O(n) 化)
                if finished_sounds:
                    finished_set = set(id(snd) for snd in finished_sounds)
                    with self.lock:
                        self.active_sounds = [snd for snd in self.active_sounds if id(snd) not in finished_set]

                # Clip and convert to signed 16-bit bytes
                output = np.clip(output_buf, -32768, 32767).astype(np.int16)
                self.played_frames += required_frames
                required_frames = yield output.tobytes()

        else:
            # --- フォールバック: スライス演算パス (numpy 不使用) ---
            while True:
                required_samples = required_frames * nchannels
                output_list = [0] * required_samples
                finished_sounds = []

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

                # Clip and convert to signed 16-bit array
                # リスト内包表記と三項演算子で高速化
                clipped = [
                    32767 if val > 32767 else (-32768 if val < -32768 else val)
                    for val in output_list
                ]
                output = array.array('h', clipped)
                self.played_frames += required_frames
                required_frames = yield output.tobytes()

    def load_sound(self, sound_id, file_path):
        """音源ファイルをデコードしてメモリにロードする"""
        if not os.path.exists(file_path):
            return False

        real_path = os.path.realpath(file_path)
        if real_path in self._file_cache:
            self.sounds[sound_id] = self._file_cache[real_path]
            return True

        file_size = os.path.getsize(file_path)
        if file_size > _MAX_AUDIO_FILE_SIZE:
            basename = os.path.basename(file_path)
            self.load_errors.append(
                f"[Audio Load Error]\n  File  : {basename}\n  Reason: Audio file too large ({file_size} bytes, limit is {_MAX_AUDIO_FILE_SIZE} bytes)"
            )
            return False
        # デコード前に再生時間だけを取得して上限チェック（OOM 攻撃対策）
        try:
            info = miniaudio.get_file_info(file_path)
            if info.duration > _MAX_AUDIO_DURATION_SEC:
                basename = os.path.basename(file_path)
                self.load_errors.append(
                    f"[Audio Load Error]\n  File  : {basename}\n"
                    f"  Reason: Audio duration too long "
                    f"({info.duration:.1f}s, limit is {_MAX_AUDIO_DURATION_SEC}s)"
                )
                return False
        except miniaudio.DecodeError:
            # get_file_info が失敗した場合はそのまま decode_file に任せる
            pass

        try:
            # PlaybackDevice と同一のフォーマット（SIGNED16 + 設定チャンネル数 + 設定レート）にデコードする
            sound = miniaudio.decode_file(
                file_path,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=self.nchannels,
                sample_rate=self.sample_rate
            )
            # 16bit = 1サンプル2バイト
            sound_bytes = len(sound.samples) * 2
            if self.total_pcm_bytes + sound_bytes > self.max_memory_bytes:
                basename = os.path.basename(file_path)
                limit_mb = self.max_memory_bytes // (1024 * 1024)
                used_mb = self.total_pcm_bytes // (1024 * 1024)
                self.load_errors.append(
                    f"[Audio Load Error]\n  File  : {basename}\n  Reason: Audio memory limit exceeded ({used_mb}MB / limit: {limit_mb}MB)"
                )
                return False

            self.sounds[sound_id] = sound
            self._file_cache[real_path] = sound
            self.total_pcm_bytes += sound_bytes
            return True
        except Exception as e:
            # curses 表示のために print せずリストに蓄積する
            basename = os.path.basename(file_path)
            self.load_errors.append(
                f"[Audio Load Error]\n  File  : {basename}\n  Reason: {e}"
            )
            return False

    def load_wav_table(self, wav_table, base_path):
        """BMSのWAVテーブルに基づいて音源を一括ロードする（同期版）"""
        for sound_id, file_name in wav_table.items():
            resolved_path = resolve_audio_path(base_path, file_name)
            if not resolved_path:
                self.load_errors.append(
                    f"[Audio Warning]\n  ID    : {sound_id}\n  Reason: File not found: {file_name}"
                )
            else:
                self.load_sound(sound_id, resolved_path)

    def load_wav_table_async(self, wav_table, base_path, on_done=None):
        """BMSのWAVテーブルに基づいて音源をバックグラウンドスレッドでロードする。

        ロード完了後に on_done コールバック（引数なし）が呼ばれる（省略可）。
        ロード状態は is_loading / loading_progress プロパティで確認できる。
        """
        self._loaded_count = 0
        self._total_count = len(wav_table)

        def _worker():
            for sound_id, file_name in wav_table.items():
                resolved_path = resolve_audio_path(base_path, file_name)
                if resolved_path:
                    self.load_sound(sound_id, resolved_path)
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

    def reset_clock(self):
        """オーディオマスタークロック（フレーム数）をリセット"""
        with self.lock:
            self.played_frames = 0

    def get_audio_time(self) -> float:
        """再生済みオーディオフレーム数に基づく現在時刻（秒）を返す"""
        with self.lock:
            return self.played_frames / self.sample_rate

    def stop_all(self):
        """すべての音を停止"""
        with self.lock:
            self.active_sounds.clear()
            self.played_frames = 0

    def close(self):
        """デバイスを閉じる"""
        self.device.close()

if __name__ == "__main__":
    import time
    print("Testing Audio Engine with manual mixer...")
    ae = AudioEngine()
    print(f"Initialized: sample_rate={ae.sample_rate}, nchannels={ae.nchannels}")
    ae.close()
