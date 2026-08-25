# Shinonome Mini – A minimal console BMS player

Python で実装された、ターミナル上で動作するシンプルな BMS プレイヤーです。
- `curses` による軽量 UI
- 音声は **miniaudio**（純粋 Python ライブラリ）で再生

## 主な機能
- **bms / bmson対応**
- **SP(5,7keys), DP(10,14keys)対応**
- **AUTO PLAY / MIRROR / RANDOM / EASY / HARD** オプションを UI で切替
- `settings.toml` にキー割り当て・設定を外部化
- オフライン、ファイル出力なし
- "SOLID"ゲージ: 初期値60%だがさらにゲージが硬いオプション

## 必要環境
- Python 3.10 以上
- ALSA / PulseAudio 等、**miniaudio** が利用できるオーディオ環境
- **pynput**（任意） – Shift / Ctrl / Alt キー判定のみに使用しています。
- **numpy**（任意） – CPU負荷軽減のため、可能なら入れることをおすすめします。
- その他標準ライブラリ (curses, json, re, os)

## セットアップ手順
```bash
# 1. 仮想環境作成
python3 -m venv venv

# 2. 仮想環境有効化（Linux/macOS）
source venv/bin/activate
# Windows の場合: venv\\Scripts\\activate

# 3. 必要パッケージをインストール
pip3 install miniaudio pynput numpy
# pkg install python-numpy # termuxなど
```

## 実行例
```bash
python3 main.py path/to/your_chart.bms
```
- **Esc** キーで終了します。（設定で変更可）
- 表示がおかしかったらterminalをfullscreenにしたりフォントサイズを小さくして調整してください。

## playlists
```bash
python3 bmsfd.py
```
- fdライクなプレイリストです。
- 上下キー(またはk/j)でカーソル移動、enterで選択orプレイ、backspaceで親ディレクトリに戻る、escで終了です。
- 「l」キーでサブディレクトリのbmsを全て一覧表示します。（量が多いと時間がかかります）もう一度押すとtoggleします。
- 先にsettings.tomlでお持ちのbmsがあるフォルダをallowed_rootsに設定しておいてください。

## メニュー画面例
- 各キーでオプションを切り替え、Enterで開始します。
```
Shinonome-Mini -- Minimal Console BMS Player
  Song: ^☆^ さくらなみこのかぜ ^☆^ / Artist: #ねここ14歳(obj:futher)
  Audio ready.

  === PLAY OPTIONS ===
    [A] AUTO PLAY    : ON
    [S] AUTO SCRATCH : OFF
    [M] MIRROR       : OFF
    [R] RANDOM       : OFF
    [E] EASY         : OFF
    [H] HARD GAUGE   : OFF
    [O] SHOW MEASURES: ON
    [keyup/down] HS (Hispeed) : 1.2
    [L] SCRATCH SIDE : LEFT
    [$] SOLID GAUGE  : OFF

  Press key [A/S/M/R/E/H/O/L/$] to toggle option.

  Press [Enter] to START PLAY
  Press [esc] to Quit
```

## ゲーム画面例
- 白鍵は[]、黒鍵は::、スクラッチはXX、ロングノートは | 、地雷は M! で表示されます。
```
  Shinonome-Mini -- Minimal Console BMS Player
  Song: ^☆^ さくらなみこのかぜ ^☆^ / Artist: #ねここ14歳(obj:futher)
  BPM: 931.0 | Time: 123.80s | HS: 100.0

    |    |[]  |    |[]  |    |[]  |    |[]  | HARD SOLID: [============----|----]  60.0%
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    | EX SCORE:     0 /  3240
    |    |[]  |    |[]  |    |[]  |    |[]  | COMBO   :     0  (MAX:     0)
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    | P:   0 G:   0 g:   0 B:   0 M:   0
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    |
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    |
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |::  |    |::  |    |
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |    |    |    |    |
  * +----+----+FL--+----+----+----+FL--+----+
  /  [S]  [1]  [2]  [3]  [4]  [5]  [6]  [7]
    [       AUTOPLAY MODE ACTIVE       ]

    Press esc to quit playing
```
## CLI options
```
--soundonly #画面なし、曲再生のみ
--nomenu #settings.tomlの設定でゲーム開始
--random, -r
--mirror, -m
--easy, -e
--hard, -h
--auto, -a
--autoscratch, -s
--solid
--mode=4k #ゲームモード強制
--mode=5k
--mode=6k
--mode=7k
--mode=9k
--mode=10k
--mode=14k
--mini #デフォルトの画面
(--tiny #もっと小さい画面 (将来実装用))
```
## Notes & Caveats
- UIはterminalだけです。グラフィカルUIはありません。
- 一部の BMS コマンドのみ対応。BMP, BGA 等はスキップします。
- **pynput** で **Shift / Ctrl / Alt** キーの判定に対応しています。
- Wayland 環境では `onrelease` が利用できないため、ロングノートの離した時の判定は未実装（consoleで行う限り実装不可）です。

## SOLIDゲージ
- 初期値60%、80%以上でクリアですが、ゲージが増減共に硬い（増えにくく減りにくい）オプションです。
   - 増加量も減少量も1/3(ゲージ70%時点)なので既存のゲームバランスを壊しません。
- HARDゲージは「ゲージが0%に近いほど減少量が少ない」のに対して、SOLIDゲージは「ゲージが100%に近いほど増加量が少ない」です。
- 増加量は通常の：{0%: 2/3, 50%: 1/2, 70%: 1/3, 80%: 1/4, 90%: 1/8, 95%: 1/16, 99%: 1/75}程度です。
- 減少量は、HARDと併用した場合にはそのまま、それ以外のモードでは通常の1/3（poor:-2%、EASYはさらに半分）です。

## 設定 (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – 各レーンとスクラッチに好みのキーを割り当てます（デフォルトは `z s x d …` ）
- Hispeed 変更ボタンのデフォルト動作を `keyup`/`keydown` に変更しました。設定でカスタマイズ可能です。
- **play_options** – オートプレイ、ミラー、ランダム、イージー、ハードなどの切り替えを行います。
- **judgement** – 判定ラインの位置やタイミングオフセットを調整します。
- 音がブツブツ切れるときは、audioセクションでサンプリングレートを下げ、モノラルに設定してください。
   - numpyがインストールされているかもチェックしてください。
- デフォルトの文字コードにはshift-jis(cp932), euc-kr(cp949), utf-8を設定できます。

## ライセンス
- GPLv3

## 謝辞
- こちらのプロジェクト [shinonome](https://github.com/kuroclef/shinonome) の作者様に感謝を申し上げます。
- 全く別物になっていますが、基本コンセプトをお借りしているので‑miniとさせていただきました。

## あとでやる(ver2.50まで)
- 画面表示オプション（--tiny: ノーツのみ、表示幅・高さも縮小）

## minimalに保つためやらない
- 画像・動画表示
- hidden/sudden, S-RAN/H-RAN/R-RAN, FLIP(DP), etc
- スコア記録・保存・送信、ファイル出力
- IR等オンライン接続
- ZZ（即死）地雷、不可視ノーツ、FREEZONE
- マイナスBPM、負のSCROLL
   - 負のSCROLL（ノーツの逆流）は譜面によっては動作することを確認しています。
   - 私が十分な量の#SCROLL(bms)やscroll_event(bmson)を使ったbmsを持っていないので仮対応です。
- midi対応
- mp3は再生できますが音ズレがあるのでおすすめしません
- preview
- bmm, 774, n2s, gda, sm, osu等他の形式
- ロングノートは見た目だけです（キーを離した判定ができないため）。そのためLN,CN,HCNの区別もありません。
   - 押しっぱなしにすると次のノートでBADをとられる場合があるので少し早めに離してください。
- ミュージックボックスを使う（昔の）bms
- #WAVに絶対パスや親ディレクトリを指定したbms
- #STP, #SPEED, #EXT, #SWITCH, etc
- 18keys, 24keys, 48keys, etc

## todoあとで確認
- wav,bmp等がサブフォルダにわかれているbmsの動作確認
- ロングノートの複雑な仕様の再確認（lnobj, lnmode, ln_type）
- bmsonのときbpm確認（1ずれない？）
- bmsonのとき実質無音ノーツになってる？
- global変数使うな
- *.pyが散らばってきたのでディレクトリ分ける
- do more tests, do more bms.

## changelog
- ver1.50 基本的なbms再生(BPM変更、小節長変更、STOP、ロングノート、etc)
- 1.53a BASE命令（36,62）
- 1.53a 多重再生の改善（do not playback many-time with single #WAVxx definition）
   - bmsonではpolyphonyに該当する仕様
- 1.53b pynput use or nouse flag by setting
- 1.56 flac対応
- 1.57c numpy(cpu負荷軽減)
- 1.58 bmsのデフォルトエンコーディング指定(shift-jis, euc-kr, utf-8)
- 1.59e++ #SCROLL命令
- 1.60 地雷ノーツ
- 1.60 #RANDOM〜#IF
- 1.61c 5keys/10keys
- 1.62 9keys(pms), #RANDOM手直し
- 1.63 4keys/6keys
- 1.64 cli options
- 1.65 add playlists (bmsfd.py), fix 4keys/6keys ch
