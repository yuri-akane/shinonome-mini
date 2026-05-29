import time
import os
from audio import AudioEngine
from parser import BmsonParser, BmsParser

import config



class Player:
    def __init__(self, audio_engine, channel_to_lane):
        self.audio = audio_engine
        self.channel_to_lane = channel_to_lane
        self.chart = None
        self.is_playing = False
        self.start_time = 0
        self.resolution = 480 # bmson default
        self.auto_scratch = False
        
        # 判定・演出関連
        self.last_judgement = "" # "PERFECT", "GREAT", "GOOD", "BAD", "MISS"
        self.judgement_time = 0 # 判定が発生した時刻
        self.key_pressed_time = [0.0] * 16 # 各レーン(0〜15)の最終打鍵時刻 (演出用)
        
        # ゲージ・スコア・統計情報
        self.gauge = 22.0 # グルーヴゲージ (初期値 22%)
        self.ex_score = 0 # EXスコア (PERFECT=2, GREAT=1)
        self.combo = 0
        self.max_combo = 0
        self.perfect_count = 0
        self.great_count = 0
        self.good_count = 0
        self.bad_count = 0
        self.miss_count = 0
        self.total_playable_notes = 0 # 総プレイノーツ数

    def load_chart(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.bmson':
            parser = BmsonParser()
            self.resolution = 480 # bmson default
        else:
            parser = BmsParser()
            self.resolution = 1.0 # BMSは拍単位で計算

        self.chart = parser.parse(file_path)
        # Load audio assets if present
        if 'wav_table' in self.chart:
            self.audio.load_wav_table(self.chart['wav_table'], self.chart['base_path'])
        # Detect DP / SP mode from #PLAYER directive in the BMS file
        # Default to SP if not found or parsing fails. #PLAYER 1 = SP, others = DP
        mode = 'SP'
        try:
            with open(file_path, 'r', encoding='shift-jis', errors='ignore') as f:
                for line in f:
                    if line.upper().startswith('#PLAYER'):
                        parts = line.strip().split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            player_num = int(parts[1])
                            mode = 'SP' if player_num == 1 else 'DP'
                        break
        except Exception:
            pass
        self.chart['mode'] = mode


    def get_current_time(self):
        if not self.is_playing:
            return 0
        return time.perf_counter() - self.start_time

    def get_judgement_windows(self):
        """#RANK命令とEASYオプションに基づき、判定窓（秒）を取得する"""
        rank = self.chart['info'].get('rank', 3) if self.chart else 3
        # デフォルトの判定窓 (BMS #RANK 3 = NORMAL 相当)
        # RANK: 0: VERY HARD, 1: HARD, 2: NORMAL, 3: EASY, 4: VERY EASY
        # と言いつつ、歴史的なBMS仕様では RANK 2 が NORMAL, 3 が EASY
        perf = 0.03
        great = 0.07
        good = 0.11
        bad = 0.15

        if rank == 0:     # VERY HARD
            perf, great, good, bad = 0.008, 0.024, 0.05, 0.10
        elif rank == 1:   # HARD
            perf, great, good, bad = 0.015, 0.045, 0.08, 0.12
        elif rank == 2:   # NORMAL
            perf, great, good, bad = 0.03, 0.06, 0.10, 0.15
        elif rank == 3:   # EASY
            perf, great, good, bad = 0.05, 0.10, 0.15, 0.20
        elif rank == 4:   # VERY EASY
            perf, great, good, bad = 0.10, 0.20, 0.30, 0.40

        # EASYオプションが有効な場合は、さらに判定窓を1.5倍緩くする
        if getattr(self, 'easy_mode', False):
            perf *= 1.5
            great *= 1.5
            good *= 1.5
            bad *= 1.5

        return perf, great, good, bad

    def get_gauge_increment(self):
        """#TOTAL命令に基づき、ノーツ1つあたりのゲージ増加量を動的計算する"""
        # デフォルトの合計ゲージ量TOTALは 160 + 0.16 * 総ノーツ数
        total_playable = max(1, self.total_playable_notes)
        default_total = 160.0 + 0.16 * total_playable
        total = self.chart['info'].get('total') if self.chart else None
        if total is None:
            total = default_total
        
        # PERFECT/GREAT時の増加量 (総ノーツを全てPERFECT/GREATで叩いたときにTOTAL%増えるようにする)
        inc = float(total) / total_playable
        return inc

    def press_key(self, lane_index):
        """プレイヤーがキーを押したときの判定処理"""
        if not self.is_playing or not self.chart:
            return
            
        current_time = self.get_current_time()
        
        # 打鍵時間を記録 (演出用)
        self.key_pressed_time[lane_index] = current_time
        
        events = self.chart['events']
        initial_bpm = self.chart['info']['bpm']
        
        # 該当レーンの未処理（state == 0）のプレイノーツを探す
        playable_events = []
        for event in events:
            if event['state'] == 0 and event['is_playable']:
                channel = event.get('channel')
                if self.channel_to_lane.get(channel) == lane_index:
                    playable_events.append(event)
                    
        if not playable_events:
            return # 叩けるノーツがない
            
        # 最も現在の時間に近いノーツを探す
        best_event = None
        min_diff = 999.0
        
        for event in playable_events:
            # Adjust timing: for BMS (resolution == 1.0) use direct beat conversion
            if self.resolution == 1.0:
                target_seconds = event['time'] * (60 / initial_bpm)
            else:
                target_seconds = (event['time'] / self.resolution) * (60 / initial_bpm)
            diff = abs(target_seconds - current_time)
            if diff < min_diff:
                min_diff = diff
                best_event = event
                
        # 判定窓の取得
        perf_w, great_w, good_w, bad_w = self.get_judgement_windows()
        # タイミングの調整値を反映 (settings.tomlのタイミングオフセット)
        # 後で設定ローダーから player.judgement_offset_ms を代入する予定
        offset_seconds = getattr(self, 'judgement_offset_ms', 0) / 1000.0
        adjusted_diff = abs((best_event['time'] * (60 / initial_bpm) if self.resolution == 1.0 else (best_event['time'] / self.resolution) * (60 / initial_bpm)) + offset_seconds - current_time) if best_event else min_diff

        # 判定窓（BAD以内）ならHIT
        if best_event and adjusted_diff <= bad_w:
            best_event['state'] = 1 # HIT状態にする
            self.audio.play(best_event['sound_id'])
            
            # 動的ゲージ増加量の取得
            inc = self.get_gauge_increment()
            
            # イージーモード時はゲージ減少量を半分にする
            loss_factor = 0.5 if getattr(self, 'easy_mode', False) else 1.0

            # 判定文字・スコア・ゲージ・コンボの割り当て
            if adjusted_diff <= perf_w:
                self.last_judgement = "PERFECT"
                self.ex_score += 2
                self.perfect_count += 1
                self.combo += 1
                self.gauge = min(100.0, self.gauge + inc)
            elif adjusted_diff <= great_w:
                self.last_judgement = "GREAT"
                self.ex_score += 1
                self.great_count += 1
                self.combo += 1
                self.gauge = min(100.0, self.gauge + inc)
            elif adjusted_diff <= good_w:
                self.last_judgement = "GOOD"
                self.good_count += 1
                self.combo += 1
                self.gauge = min(100.0, self.gauge + (inc * 0.5))
            else:
                self.last_judgement = "BAD"
                self.bad_count += 1
                self.combo = 0
                self.gauge = max(0.0, self.gauge - (4.0 * loss_factor))
                
            self.max_combo = max(self.max_combo, self.combo)
            self.judgement_time = current_time

    def play(self, on_update=None, auto_play=True):
        if not self.chart:
            return

        self.is_playing = True
        self.last_judgement = ""
        self.judgement_time = 0
        self.key_pressed_time = [0.0] * 16
        
        # 統計情報の初期化
        self.gauge = 22.0
        self.ex_score = 0
        self.combo = 0
        self.max_combo = 0
        self.perfect_count = 0
        self.great_count = 0
        self.good_count = 0
        self.bad_count = 0
        self.miss_count = 0
        
        events = self.chart['events']
        initial_bpm = self.chart['info']['bpm']
        
        # 各ノーツのプレイ可否と初期状態のセットアップ、総ノーツ数の集計
        self.total_playable_notes = 0
        for event in events:
            channel = event.get('channel', '01')
            event['is_playable'] = channel in self.channel_to_lane
            event['state'] = 0 # 0: PENDING, 1: HIT (or BGM processed), 2: MISS
            if event['is_playable']:
                self.total_playable_notes += 1
            
        self.start_time = time.perf_counter()
        event_index = 0
        
        while self.is_playing:
            current_time = self.get_current_time()
            
            # 全イベントが処理済みになったかチェック
            all_processed = True
            for event in events:
                if event['state'] == 0:
                    all_processed = False
                    break
            
            # 自動発音（BGM または AutoPlay時のプレイノーツ）
            while event_index < len(events):
                event = events[event_index]
                # Adjust timing for BMS vs bmson
                if self.resolution == 1.0:
                    target_seconds = event['time'] * (60 / initial_bpm)
                else:
                    target_seconds = (event['time'] / self.resolution) * (60 / initial_bpm)
                if current_time >= target_seconds:
                    is_scratch = False
                    if event['is_playable']:
                        lane_idx = self.channel_to_lane.get(event['channel'])
                        is_dp = (self.chart.get('mode', 'SP') == 'DP')
                        if is_dp:
                            # DPのときは最左端(0)と最右端(15)がスクラッチ
                            if lane_idx in (0, 15):
                                is_scratch = True
                        else:
                            # SPのときは、config.CHANNEL_TO_LANEでマッピングされた側がスクラッチ
                            # LEFTスクラッチはレーン0、RIGHTスクラッチはレーン7
                            # 
                            # または、動的マッピングで "16" が指すレーンインデックスを取得
                            scratch_lane = self.channel_to_lane.get("16")
                            if lane_idx == scratch_lane:
                                is_scratch = True
                    
                    # オートプレイ、BGM、またはオートスクラッチ対象のスクラッチノーツの場合
                    if auto_play or not event['is_playable'] or (self.auto_scratch and is_scratch):
                        self.audio.play(event['sound_id'])
                        event['state'] = 1 # 処理済みにする
                        if event['is_playable']:
                            # スコアなどの加算（オートスクラッチまたはオートプレイ時）
                            self.ex_score += 2
                            self.perfect_count += 1
                            self.combo += 1
                            self.max_combo = max(self.max_combo, self.combo)
                            # 動的ゲージ増加量の適用
                            inc = self.get_gauge_increment()
                            self.gauge = min(100.0, self.gauge + inc)
                            self.last_judgement = "PERFECT"
                            self.judgement_time = current_time
                            
                            lane_idx = self.channel_to_lane.get(event['channel'])
                            if lane_idx is not None:
                                self.key_pressed_time[lane_idx] = current_time
                    event_index += 1
                else:
                    break
                    
            # ManualPlay時の見逃しMISS判定
            if not auto_play:
                perf_w, great_w, good_w, bad_w = self.get_judgement_windows()
                for event in events:
                    if event['state'] == 0 and event['is_playable']:
                        # オートスクラッチが有効な場合、スクラッチノーツは見逃しMISS判定から除外する
                        if self.auto_scratch:
                            lane_idx = self.channel_to_lane.get(event['channel'])
                            is_dp = (self.chart.get('mode', 'SP') == 'DP')
                            is_scratch = False
                            if is_dp:
                                if lane_idx in (0, 15):
                                    is_scratch = True
                            else:
                                scratch_lane = self.channel_to_lane.get("16")
                                if lane_idx == scratch_lane:
                                    is_scratch = True
                            if is_scratch:
                                continue
                        
                        target_seconds = (event['time'] / self.resolution) * (60 / initial_bpm)
                        offset_seconds = getattr(self, 'judgement_offset_ms', 0) / 1000.0
                        # 判定（BAD窓）を過ぎたら自動的にMISS
                        if current_time - (target_seconds + offset_seconds) > bad_w:
                            event['state'] = 2
                            self.last_judgement = "MISS"
                            self.miss_count += 1
                            self.combo = 0
                            # イージーモード時はMISS時のゲージ減少量を半分にする
                            loss_factor = 0.5 if getattr(self, 'easy_mode', False) else 1.0
                            self.gauge = max(0.0, self.gauge - (6.0 * loss_factor))
                            self.judgement_time = current_time
                            
            # 終了条件：全イベントが処理され、かつ再生中の音がすべて消えた
            if all_processed and len(self.audio.active_sounds) == 0:
                break
                
            # 描画コールバックの呼び出し
            if on_update:
                on_update(current_time, events, event_index, initial_bpm, self.resolution, auto_play)
                
            time.sleep(0.01) # 100 FPS
            
        self.is_playing = False

if __name__ == "__main__":
    print("Player logic ready.")
