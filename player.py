import time
import os
from audio import AudioEngine
from parser import BmsonParser, BmsParser
import config

class Player:
    def __init__(self, audio_engine, channel_to_lane):
        self.audio = audio_engine
        self.channel_to_lane = channel_to_lane
        self.debug = False
        self.chart = None
        self.is_playing = False
        self.start_time = 0
        self.resolution = 480  # bmson default
        self.auto_scratch = False
        self.hard_mode = False
        self.is_dead = False

        # 判定・演出関連
        self.last_judgement = ""  # "PERFECT", "GREAT", "GOOD", "BAD", "MISS"
        self.judgement_time = 0  # 判定が発生した時刻
        self.key_pressed_time = [0.0] * 16  # 各レーン(0〜15)の最終打鍵時刻 (演出用)

        # ゲージ・スコア・統計情報
        self.gauge = 22.0  # グルーヴゲージ (初期値 22%)
        self.ex_score = 0  # EXスコア (PERFECT=2, GREAT=1)
        self.combo = 0
        self.max_combo = 0
        self.perfect_count = 0
        self.great_count = 0
        self.good_count = 0
        self.bad_count = 0
        self.miss_count = 0
        self.total_playable_notes = 0  # 総プレイノーツ数
        self.active_lns = {}  # lane_index -> start_event
        self.last_key_press_time = [0.0] * 16
        self.last_any_key_press_time = 0.0

    def _init_event_state(self):
        """Initialize event flags and count playable notes.
        Called after loading a chart to separate concerns from the playback loop.
        """
        events = self.chart.get('events', [])
        self.total_playable_notes = 0
        for event in events:
            channel = event.get('channel', '01')
            event['is_playable'] = (channel in self.channel_to_lane) or (channel.isdigit() and 51 <= int(channel) <= 69)
            event['state'] = 0  # 0: PENDING, 1: HIT (or BGM processed), 2: MISS
            if event['is_playable']:
                if event.get('ln_state') == 'end':
                    continue
                self.total_playable_notes += 1

    def apply_measure_change(self, event):
        """Update current measure length multiplier based on a measure change event.
        This separates measure-length handling from BPM handling.
        """
        self.current_measure_multiplier = event.get('measure_mult', 1.0)

    def apply_bpm_change(self, event):
        """Update current BPM based on a BPM change event.
        Centralizes BPM state mutation and updates speed factor for UI scaling.
        """
        self.current_bpm = event['bpm']
        if getattr(self, 'initial_bpm', None):
            self.speed_factor = self.current_bpm / self.initial_bpm


    def load_chart(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.bmson':
            parser = BmsonParser()
            self.resolution = 480 # bmson default
        else:
            parser = BmsParser()
            self.resolution = 1.0 # BMSは拍単位で計算

        try:
            self.chart = parser.parse(file_path)
            # After parsing, store the initial BPM for reference and speed scaling
            self.initial_bpm = self.chart['info']['bpm']
            self.current_bpm = self.initial_bpm  # current BPM starts as initial
            # Speed factor (relative to initial BPM) used by UI for visual fall speed
            self.speed_factor = 1.0
            self.timeline = self.chart.get('timeline', None)
            # bmsonファイルかどうかをフラグとして保持（total値の解釈が異なる）
            self.chart['is_bmson'] = (ext == '.bmson')
            #self._debug_log(f"Initial BPM set to {self.initial_bpm}")
        except Exception as e:
            #self._debug_log(f"Error loading chart: {e}")
            raise
        # Detect DP / SP mode from #PLAYER directive in the BMS file
        # Default to SP if not found or parsing fails. #PLAYER 1 = SP, others = DP.
        # For bmson files, respect the mode determined by the parser.
        if ext == '.bmson':
            mode = self.chart['info'].get('mode', 'SP')
        else:
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

    def load_audio_async(self):
        """チャートのWAVテーブルをバックグラウンドでロード開始する。
        load_chart() の完了後に呼び出すこと。
        ロード状態は is_audio_ready プロパティで確認できる。
        """
        if self.chart and 'wav_table' in self.chart:
            self.audio.load_wav_table_async(
                self.chart['wav_table'],
                self.chart['base_path']
            )

    @property
    def is_audio_ready(self):
        """音声リソースのロードが完了して再生可能な状態かどうか。
        チャートがない場合やWAVテーブルがない場合は True を返す。
        """
        return not self.audio.is_loading

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
            bad *= 1.4 # 1.5 #badハマりがゲーム性を損なうのでせめてもの抵抗

        return perf, great, good, bad

    def get_gauge_increment(self):
        """#TOTAL命令に基づき、ノーツ1つあたりのゲージ増加量を動的計算する

        BMS: #TOTAL は「全ノーツをPERFECTで叩いたときのゲージ増加量合計(%)」の絶対値。
             increment = total / note_count
        bmson: total は「デフォルトレートに対する相対乗数」(デフォルト=100)。
             increment = estimated_total(note_count) * (total / 100) / note_count
        """
        total_playable = max(1, self.total_playable_notes)
        total = self.chart['info'].get('total') if self.chart else None
        is_bmson = self.chart.get('is_bmson', False) if self.chart else False

        if is_bmson:
            # bmson: total は相対値(デフォルト=100)。
            # parserでtotalが0以下や未設定のときはestimated_total()で埋めてあるので基本的には来ないが念のため。
            from timing import estimated_total
            if total is None or total < 0:
                total = 100.0  # デフォルト値
            base = estimated_total(total_playable)
            # PERFECT/GREAT時の増加量 = デフォルトレート × 相対乗数
            return base * (float(total) / 100.0) / total_playable
        else:
            # BMS: total は絶対値（全PERFECT時のゲージ増加量合計%）
            if total is None:  # parserで処理できてればそもそもここに来ないはずだが…
                from timing import estimated_total
                total = estimated_total(total_playable)
            # PERFECT/GREAT時の増加量 (総ノーツを全てPERFECT/GREATで叩いたときにTOTAL%増えるようにする)
            return float(total) / total_playable

    def _hard_gauge_loss(self, is_miss: bool) -> float:
        """HARDゲージのBAD/MISS時ゲージ減少量を計算する（負の値を返す）。
        現在のゲージ量 x = gauge/100 に応じた補正関数を使用する。
          f(x) = 1 - (1-x)^2
          BAD : -(1 + 4*f(x))
          MISS: -(2 + 8*f(x))
        ゲージが高いほど減少量が大きく、低いほど減少量が小さい。
        """
        x = self.gauge / 100.0
        fx = 1.0 - (1.0 - x) ** 2
        if is_miss:
            return -(2.0 + 8.0 * fx)
        else:
            return -(1.0 + 4.0 * fx)

    def _get_polyphony_limit(self, sound_id):
        if not self.chart:
            return 1
        # bmsonの場合はpolyphony_tableの値を取得、なければ1。BMS形式の場合は常に1とする。
        if self.chart.get('is_bmson', False):
            return self.chart.get('polyphony_table', {}).get(sound_id, 1)
        return 1

    def press_key(self, lane_index):
        """プレイヤーがキーを押したときの判定処理"""
        if not self.is_playing or not self.chart:
            return

        current_time = self.get_current_time()

        # 打鍵時間を記録 (演出用)
        self.key_pressed_time[lane_index] = current_time
        self.last_key_press_time[lane_index] = current_time

        # もし該当レーンでロングノートがアクティブ（押しっぱなし中）なら、リピート入力は無視する
        if lane_index in self.active_lns:
            return

        self.last_any_key_press_time = current_time

        events = self.chart['events']
        initial_bpm = self.chart['info']['bpm']

        # 該当レーンの未処理（state == 0）のプレイノーツを探す
        # ただし、ロングノートの終端は press_key で直接叩くものではないため除外する
        playable_events = []
        for event in events:
            if event['state'] == 0 and event['is_playable']:
                if event.get('ln_state') == 'end':
                    continue
                channel = event.get('channel')
                if self.channel_to_lane.get(channel) == lane_index:
                    playable_events.append(event)

        if not playable_events:
            return # 叩けるノーツがない

        # 最も現在の時間に近いノーツを探す
        best_event = None
        min_diff = 999.0

        for event in playable_events:
            diff = abs(event['time'] - current_time)
            if diff < min_diff:
                min_diff = diff
                best_event = event

        # 判定窓の取得
        perf_w, great_w, good_w, bad_w = self.get_judgement_windows()
        # タイミングの調整値を反映 (settings.tomlのタイミングオフセット)
        # 後で設定ローダーから player.judgement_offset_ms を代入する予定
        offset_seconds = getattr(self, 'judgement_offset_ms', 0) / 1000.0
        adjusted_diff = abs(best_event['time'] + offset_seconds - current_time) if best_event else min_diff

        # 判定窓（BAD以内）ならHIT
        if best_event and adjusted_diff <= bad_w:
            best_event['state'] = 1 # HIT状態にする
            if best_event.get('sound_id'):
                limit = self._get_polyphony_limit(best_event['sound_id'])
                self.audio.play(best_event['sound_id'], limit)

            # 動的ゲージ増加量の取得
            inc = self.get_gauge_increment()

            # モード別のゲージ増加倍率を決定
            if self.hard_mode:
                # HARDゲージ: 回復量を抑制
                perf_mult, great_mult, good_mult = 0.2, 0.15, 0.1
            else:
                # イージーモード時はゲージ減少量を半分にする
                loss_factor = 0.5 if getattr(self, 'easy_mode', False) else 1.0
                perf_mult, great_mult, good_mult = 1.0, 1.0, 0.5

            is_hit = False
            # 判定文字・スコア・ゲージ・コンボの割り当て
            if adjusted_diff <= perf_w:
                self.last_judgement = "PERFECT"
                self.ex_score += 2
                self.perfect_count += 1
                self.combo += 1
                self.gauge = min(100.0, self.gauge + inc * perf_mult)
                is_hit = True
            elif adjusted_diff <= great_w:
                self.last_judgement = "GREAT"
                self.ex_score += 1
                self.great_count += 1
                self.combo += 1
                self.gauge = min(100.0, self.gauge + inc * great_mult)
                is_hit = True
            elif adjusted_diff <= good_w:
                self.last_judgement = "GOOD"
                self.good_count += 1
                self.combo += 1
                self.gauge = min(100.0, self.gauge + inc * good_mult)
                is_hit = True
            else:
                self.last_judgement = "BAD"
                self.bad_count += 1
                self.combo = 0
                if self.hard_mode:
                    loss = self._hard_gauge_loss(is_miss=False)
                    self.gauge = max(0.0, self.gauge + loss)
                    if self.gauge <= 0.0:
                        self.is_dead = True
                        self.is_playing = False
                else:
                    self.gauge = max(0.0, self.gauge - (4.0 * loss_factor))

            # # ロングノートの始点ノーツを正しく叩けた場合、アクティブにする
            if is_hit and best_event.get('ln_state') == 'start':
                self.active_lns[lane_index] = best_event

            self.max_combo = max(self.max_combo, self.combo)
            self.judgement_time = current_time

    def play(self, on_update=None, auto_play=True):
        if not self.chart:
            return

        self.is_playing = True
        self.last_judgement = ""
        self.judgement_time = 0
        self.key_pressed_time = [0.0] * 16
        self.last_key_press_time = [0.0] * 16
        self.active_lns.clear()

        # 統計情報の初期化
        self.gauge = 100.0 if self.hard_mode else 22.0
        self.is_dead = False
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
        # Prepare event flags and count playable notes
        self._init_event_state()

        #self._debug_log("=== First 10 events (beat, time) ===")
        #for i, ev in enumerate(events[:10]):
        #    self._debug_log(f"{i}: beat={ev.get('beat')}, time={ev.get('time')}")
        self.start_time = time.perf_counter()
        event_index = 0
        self.current_bpm = initial_bpm

        while self.is_playing:
            current_time = self.get_current_time()

            # 全イベントが処理済みになったかチェック
            all_processed = True
            for event in events:
                if event['state'] == 0:
                    all_processed = False
                    break

            # 自動発音（BGM または AutoPlay時のプレイノーツ、およびBPM変化イベント）
            while event_index < len(events):
                event = events[event_index]
                target_seconds = event['time']

                # Both control events and audio triggers must wait until their target time is reached
                if current_time >= target_seconds:
                    # Process control events (BPM or measure changes)
                    from control import process_control_event
                    old_bpm = self.current_bpm
                    old_mult = getattr(self, 'current_measure_multiplier', 1.0)
                    if process_control_event(self, event, auto_play):
                        event['state'] = 1
                        event_index += 1
                        continue

                    if event['channel'] == '01':
                        # Always play BGM regardless of is_playable or auto_play
                        if event.get('sound_id'):
                            limit = self._get_polyphony_limit(event['sound_id'])
                            self.audio.play(event['sound_id'], limit)
                        event['state'] = 1
                    elif event['channel'] == 'measure_line':
                        event['state'] = 1
                    elif event['is_playable']:
                        # Handle end of long note automatically
                        if event.get('ln_state') == 'end':
                            # 終端処理成功：コンボ・ゲージは特に増やさない
                            # Remove from active_lns if present
                            lane_idx = self.channel_to_lane.get(event.get('channel'))
                            if lane_idx in self.active_lns:
                                del self.active_lns[lane_idx]
                            event['state'] = 1
                            event_index += 1
                            continue

                        # Determine if this event is a scratch note
                        channel = event.get('channel')
                        lane_idx = self.channel_to_lane.get(channel)
                        is_dp = (self.chart.get('mode', 'SP') == 'DP')
                        is_scratch = False
                        if lane_idx is not None:
                             if is_dp:
                                 is_scratch = (lane_idx in (0, 15))
                             else:
                                 # In SP mode, only channel "16" is considered scratch
                                 is_scratch = (channel == "16")

                        if auto_play or (self.auto_scratch and is_scratch):
                            if event.get('sound_id'):
                                limit = self._get_polyphony_limit(event['sound_id'])
                                self.audio.play(event['sound_id'], limit)
                            event['state'] = 1
                    event_index += 1
                    continue
                else:
                    break

            #             if self.last_any_key_press_time > self.last_key_press_time[lane_idx]:
            #                 continue
            #             # 途中で離した場合はBAD！
            #             end_ev = start_ev.get('ln_partner')
            #             if end_ev and end_ev['state'] == 0:
            #                 end_ev['state'] = 2  # MISS/BAD扱いの処理済み状態
            #                 self.last_judgement = "BAD"
            #                 self.bad_count += 1
            #                 self.combo = 0
            #                 self.gauge = max(0.0, self.gauge - (4.0 * loss_factor))
            #                 self.judgement_time = current_time
            #             del self.active_lns[lane_idx]
            #         else:
            #             # 終端に到達したか確認
            #             end_ev = start_ev.get('ln_partner')
            #             if end_ev and current_time >= end_ev['time']:
            #                 end_ev['state'] = 1  # HIT状態にする
            #                 # self.audio.play(end_ev['sound_id'])  # Removed to prevent double sound on LN end
            #                 # 終端処理成功：コンボを1増やし、ゲージを少し回復
            #                 self.combo += 1
            #                 self.max_combo = max(self.max_combo, self.combo)
            #                 inc = self.get_gauge_increment()
            #                 self.gauge = min(100.0, self.gauge + inc)
            #                 del self.active_lns[lane_idx]

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

                        target_seconds = event['time']
                        offset_seconds = getattr(self, 'judgement_offset_ms', 0) / 1000.0
                        # 判定（BAD窓）を過ぎたら自動的にMISS
                        if current_time - (target_seconds + offset_seconds) > bad_w:
                            event['state'] = 2
                            self.last_judgement = "MISS"
                            self.miss_count += 1
                            self.combo = 0
                            if self.hard_mode:
                                loss = self._hard_gauge_loss(is_miss=True)
                                self.gauge = max(0.0, self.gauge + loss)
                                if self.gauge <= 0.0:
                                    self.is_dead = True
                                    self.is_playing = False
                            else:
                                # イージーモード時はMISS時のゲージ減少量を半分にする
                                loss_factor = 0.5 if getattr(self, 'easy_mode', False) else 1.0
                                self.gauge = max(0.0, self.gauge - (6.0 * loss_factor))
                            self.judgement_time = current_time

                            # もしロングノートの始点を見逃しMISSしたなら、終端も自動的にMISS扱いにする
                            if event.get('ln_state') == 'start':
                                end_ev = event.get('ln_partner')
                                if end_ev and end_ev['state'] == 0:
                                    end_ev['state'] = 2

            # 終了条件：全イベントが処理され、かつ再生中の音がすべて消えた
            if all_processed and len(self.audio.active_sounds) == 0:
                self.is_playing = False
                break

            # 描画コールバックの呼び出し
            if on_update:
                on_update(current_time, events, event_index, self.current_bpm, self.resolution, auto_play)

            time.sleep(0.005) #PCのスペックが低い場合ここのsleepを取り除けば多少軽くなる

        self.is_playing = False

if __name__ == "__main__":
    print("Player logic ready.")
