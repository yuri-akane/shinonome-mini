import miniaudio
import os

import threading
import array

class AudioEngine:
    def __init__(self):
        self.sounds = {} # {sound_id: DecodedSoundFile}
        self.active_sounds = [] # [{"samples": array, "position": int}]
        self.lock = threading.Lock()
        
        # PlaybackDeviceの初期化 – バッファサイズは milliseconds で指定
        # 3msは攻めすぎてノイズ多いので10msに
        self.device = miniaudio.PlaybackDevice(
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=2,
            sample_rate=24000,
            buffersize_msec=10,
        )
        
        # ジェネレータの作成と起動
        self.generator = self._mix_generator()
        next(self.generator) # 最初のyieldまで進める
        
        # 再生開始
        self.device.start(self.generator)

    def _mix_generator(self):
        # Initial yield to receive the first frame count request
        required_frames = yield b""
        while True:
            required_samples = required_frames * 2
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
                for i in range(to_copy):
                    output_list[i] += src[pos + i]
                sound["position"] += to_copy
                if sound["position"] >= src_len:
                    finished_sounds.append(sound)

            # Remove finished sounds
            if finished_sounds:
                with self.lock:
                    for snd in finished_sounds:
                        if snd in self.active_sounds:
                            self.active_sounds.remove(snd)

            # Clip and convert to signed 16‑bit array
            output = array.array('h', [0] * required_samples)
            for i, val in enumerate(output_list):
                if val > 32767:
                    val = 32767
                elif val < -32768:
                    val = -32768
                output[i] = val

            # Yield mixed audio and receive next frame request
            required_frames = yield output.tobytes()

    def load_sound(self, sound_id, file_path):
        """音源ファイルをデコードしてメモリにロードする"""
        if not os.path.exists(file_path):
            return False
        try:
            # 常に SIGNED16, 2チャンネル, 24000Hz にデコードする
            sound = miniaudio.decode_file(
                file_path,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=2,
                sample_rate=24000
            )
            self.sounds[sound_id] = sound
            return True
        except Exception as e:
            # デバッグ用にログを出力
            print(f"Error loading {file_path}: {e}")
            return False

    #あとでflacにも対応すべき。mp3は要らない？
    def load_wav_table(self, wav_table, base_path):
        """BMSのWAVテーブルに基づいて音源を一括ロードする"""
        for sound_id, file_name in wav_table.items():
            file_name = file_name.replace('\\', '/')
            name, ext = os.path.splitext(file_name)
            path_no_ext = os.path.join(base_path, name)
            
            loaded = False
            for e in ['.wav', '.ogg', '.WAV', '.OGG', ext]:
                full_path = path_no_ext + e
                if os.path.exists(full_path):
                    if self.load_sound(sound_id, full_path):
                        loaded = True
                        break
            if not loaded:
                print(f"Warning: Failed to load {sound_id} ({file_name})")

    def play(self, sound_id):
        """ロード済みの音を再生する"""
        if sound_id in self.sounds:
            sound = self.sounds[sound_id]
            # 新しい再生インスタンスを作成して追加
            with self.lock:
                # Log when a sound is queued for playback
                # if not sound_id.startswith('01'): #???01はWAV01なのか12301なのか混同している？
                #     log_event('play_queued', f'sound_id={sound_id}')
                self.active_sounds.append({
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
    print("Initialization success!")
    ae.close()
