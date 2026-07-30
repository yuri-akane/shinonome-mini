import miniaudio
import os

import threading
import array

try:
    import numpy as np
    _USE_NUMPY = True
except ImportError:
    _USE_NUMPY = False

from config import load_audio_config, get_filename_variants, normalize_filename_chars

def resolve_audio_path(base_path: str, relative_file_name: str) -> str | None:
    """
    指定されたベースパスと相対ファイル名から実際の音源ファイルパスを解決する。
    - パス区切り (\\) を / に統一
    - 特殊文字（波ダッシュ、ダッシュ、マイナス記号等）の表記揺れバリエーション検索
    - 拡張子フォールバック順 (.wav -> .ogg -> .flac -> .mp3 -> 元の拡張子)
    - ディレクトリ内スキャンによる文字正規化・大文字小文字無視曖昧一致
    """
    rel_path = relative_file_name.replace('\\', '/')
    full_target = os.path.join(base_path, rel_path)

    dir_name, base_name = os.path.split(full_target)
    stem, ext = os.path.splitext(base_name)

    # 試行する拡張子の優先順位 (.wav -> .ogg -> .flac -> .mp3 -> 元の拡張子)
    candidate_exts = ['.wav', '.ogg', '.flac', '.mp3']
    if ext and ext.lower() not in candidate_exts:
        candidate_exts.append(ext.lower())

    # 1. 互換文字バリエーション (波ダッシュ、ダッシュ、マイナス記号等)
    stem_variants = get_filename_variants(stem)

    # 1-A. 直接存在判定
    for e in candidate_exts:
        ext_patterns = [e, e.upper()] if e.islower() else [e, e.lower()]
        for st in stem_variants:
            for ep in ext_patterns:
                cand_path = os.path.join(dir_name, st + ep)
                if os.path.exists(cand_path):
                    return cand_path

    # 2. ディレクトリ内スキャンによるフォールバック
    if os.path.isdir(dir_name):
        try:
            files_in_dir = os.listdir(dir_name)
        except OSError:
            files_in_dir = []

        norm_target_stem = normalize_filename_chars(stem).lower()
        norm_candidate_exts = [e.lower() for e in candidate_exts]

        for target_ext in norm_candidate_exts:
            for real_fname in files_in_dir:
                real_stem, real_ext = os.path.splitext(real_fname)
                if normalize_filename_chars(real_stem).lower() == norm_target_stem and real_ext.lower() == target_ext:
                    return os.path.join(dir_name, real_fname)

    return None

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
            resolved_path = resolve_audio_path(base_path, file_name)
            if resolved_path and self.load_sound(sound_id, resolved_path):
                pass
            else:
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
