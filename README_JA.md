# Shinonome Mini – A minimal console BMS player

Python で実装された、ターミナル上で動作するシンプルな BMS プレイヤーです。
- `curses` による軽量 UI
- 音声は **miniaudio**（純粋 Python ライブラリ）で再生
   - 他のライブラリへの依存を極力抑え、**pynput**,**numpy**のみ任意で使用としています。

## 主な機能
- **bms / bmson対応**
- **SP(5,7keys), DP(10,14keys), 9,4,6keys対応**
- **AUTO PLAY / MIRROR / RANDOM / EASY / HARD** オプションを UI で切替
- `settings.toml` にキー割り当て・設定を外部化
- オフライン、ファイル出力なし
- "SOLID"ゲージ: 初期値60%だがさらにゲージが硬いオプション

## 必要環境
- Python 3.10 以上
- ALSA / PulseAudio 等、**miniaudio** が利用できるオーディオ環境
- **pynput**（任意） – Shift / Ctrl / Alt キー判定のみに使用しています。
- **numpy**（任意） – CPU負荷軽減のため、可能なら入れることをおすすめします。
- その他標準ライブラリ (curses, json, re, os, and select (or msvcrt))
   - on Windows, pip install `windows-curses`.

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
# pip install windows-curses # windows
```

## 実行例
```bash
python3 cnnm.py path/to/your_chart.bms
```
- **Esc** キーで終了します。（設定で変更可）
- 表示がおかしかったらterminalをfullscreenにしたりフォントサイズを小さくして調整してください。
   - 調整不可能な環境の場合は--tiny（極小画面）をご使用ください。

## playlists
```bash
python3 bmsfd.py
```
- fdライクなプレイリスト（曲選択画面）です。
- 上下キー(またはk/j)でカーソル移動、enterで選択orプレイ、backspaceで親ディレクトリに戻る、escで終了です。
- 「l」キーでサブディレクトリのbmsを全て一覧表示します。（量が多いと時間がかかります）もう一度押すとtoggleします。
- 「F7」キーでadvanced mode、使用頻度が低めの詳細設定等ができます。もう一度押すとtoggleします。
- 先にsettings.tomlでお持ちのbmsがあるフォルダをallowed_rootsに設定しておいてください。
- 他のモジュールからは独立しています。
   - cnnm.py以外の他のbmsビューア・プレイヤーも呼び出せます（settings.tomlで設定）。

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

## ゲーム画面例(--mini)
- 白鍵は[]、黒鍵は::、スクラッチはXX、ロングノートは | 、地雷は M! で表示されます。(5/7/10/14keys)
   - 9/4/6keysはそれぞれ異なります。->9keys: () ^^ && >> OO << && ^^ ()
   - constants.pyの変数を書き換えることでカスタマイズできます。
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

## リザルト画面例(--mini)
```
  +------------------------------------------------+
  |                                                |
  |            S T A G E   F A I L E D             |
  |                                                |
  |          ~  Failed (Gauge: 22.0%)  ~           |
  |                                                |
  |   ---  Results  ---                            |
  |    PERFECT :     0                             |
  |    GREAT   :     0                             |
  |    GOOD    :     0                             |
  |    BAD     :     0                             |
  |    MISS    :     0                             |
  |                                                |
  |    EX SCORE :     0 /  1286                    |
  |    MAX COMBO:     0                            |
  |    MIN GAUGE:  22.0% / MAX GAUGE:  22.0%       |
  |              Press [esc] to Quit               |
  +------------------------------------------------+ 
```

## ゲーム画面例(--tiny)
- 極小表示です。ノーツのみ、表示幅・高さも縮小(7鍵の場合8x8文字、一番下はゲージ)
- 白鍵は「*」 黒鍵は「,」 スクラッチは「X」 ロングノートは「|」 地雷は「!（反転）」で表示されます。(5/7/10/14keys)
   - 9/4/6keysはそれぞれ異なります。 -> 9keys: o ^ & > o < & ^ o
   - constants.pyの変数を書き換えることでカスタマイズできます。

```例：Heavenly Door (CHALLENGE : AIR Special)
        |
        |
  * * * |
     ,  |
        |
 X*     *
  !!!!!!!
 ==------
```

## リザルト画面例(--tiny)
```
  +------------------+
  |      FAILED      |
  |   GAUGE 22.0%    |
  | P:   0  G:   0   |
  | g:   0  B:   0   |
  | M:   0           |
  | EX:    0/1286    |
  | MAX:   0         |
  |    [esc] Quit    |
  +------------------+
```

## cnnm.py CLI options
```
--soundonly #画面なし、曲再生のみ
--nomenu #settings.tomlの設定でゲーム開始
--random, -r [on|off]
--mirror, -m [on|off]
--easy, -e [on|off]
--hard, -h [on|off]
--auto, -a [on|off]
--autoscratch, -s [on|off]
--solid [on|off]
--mode=4k #ゲームモード強制 --mode-hintも同じ
--mode=5k
--mode=6k
--mode=7k
--mode=9k
--mode=10k
--mode=14k
--mini #デフォルトの画面
--tiny #極小画面
--none # --soundonlyと同じ
--help
--show-result [on|off]
--stats [on|off]
--mw #Mixwaver Mode
--scan # --mwと同じ
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
   - HARDと併用時はさらに0.1-0.2倍です。「初期値60%」です。
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

## あとでやる
- ver2.00まで
   - cnnm.py以外の他のbmsビューア・プレイヤーも引数で呼べるようにする(ok?)
- ver2.50まで
   - mixwaver-mode(ok?)
   - マイナスBPM(?)

## minimalに保つためやらない
- 画像・動画表示
- hidden/sudden, S-RAN/H-RAN/R-RAN, FLIP(DP), etc
- スコア記録・保存・送信、ファイル出力
- IR等オンライン接続
- ZZ（即死）地雷、不可視ノーツ、FREEZONE
- マイナスBPM、負のSCROLL, gravity, reverse flow
   - 負のSCROLL（ノーツの逆流）は譜面によっては動作することを確認しています。
   - 私が十分な量の#SCROLL(bms)やscroll_event(bmson)を使ったbmsを持っていないので仮対応です。
- midi対応
- mp3は再生できますが音ズレがあるのでおすすめしません
- preview
- bmm, 774, n2s, gda, sm, osu等他の形式
   - 16-17chを使用したダブルスクラッチやフットペダル
- #LNMODE x, #MGQ
   - ロングノートは見た目だけです（キーを離した判定ができないため）。そのためLN,CN,HCNの区別もありません。
   - 押しっぱなしにすると次のノートでBADをとられる場合があるので少し早めに離してください。
- ミュージックボックスを使う（昔の）bms
- #WAVに絶対パスや親ディレクトリを指定したbms
- #STP, #SPEED, #EXT, #SWITCH, %URL, %mail, #EXBPM, #BASEBPM, etc
- 18keys, 24keys, 48keys, etc
- 1000小節以上のbms、演奏に1日以上かかるbms
- half、スキン
   - separateに対する5鍵のhalf表示。代わりにはならないかもしれませんが、"tiny"表示を使ってください。
- SLOW/FAST表示、
- "白/緑文字"
- constant/max/min hispeed
- 再生自体の加速（1.5倍速再生等）
- 空打ちPOOR（とりあえずありません）
- フォルダ分け、ランダム選択、course play、段位

## todoあとで確認
- wav,bmp等がサブフォルダにわかれているbmsの動作確認
- bmsonのときbpm確認（1ずれない？）
   - 特に1分以上の1本wav等で少し音ズレしてます。bmsなら切り捨てますが、bmsonは仕様上音切りをプレイヤー側に任せうるので要調整…
   - 若干改善しましたが要確認(@ver1.79)
- bmsonのとき実質無音ノーツになってる？（音切りされていないbmsonの仕様）
- do more tests, do more bms.

## changelog
- ver1.50 基本的なbms再生(BPM変更、小節長変更、STOP、ロングノート(type1,2,lnobj)、etc)
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
- 1.65 曲選択画面としてplaylistsの追加 (bmsfd.py), fix 4keys/6keys ch
- 1.66 rename main.py->cnnm.py, fix playlists with bmson, fix 4keys/6keys mirror/random
- 1.67 bmsonの小節線命令仮対応
- 1.68 画面が小さいときのcursesエラー緩和、--tinyオプション追加、remove deprecated typing(python 3.9+)、
- 1.69 --soundonly時の動作改善（Ctrl+Cで強制終了するしかなかったのをEnterキーで終了するように修正）、windows対応の若干改善
- 1.70 --tiny画面の改善（押したキーが反転表示でわかるように、ゲームオーバー表示をtinyに合わせて小さく）
- 1.71 リザルト表示、リザルト標準出力、autoplayでゲージが増えるように、その他エラーハンドリング
- 1.72 短いロングノートの振る舞いのデバグ
- 1.73 ゲージが十分にあってもfailedになる場合があるのを修正
- 1.74 experimental MixWaver Mode
- 1.75 --modeで強制的にモード指定したときの動作の修正
- 1.76 option周りのリファクタ、リザルト画面でenterキーで終了するように
- 1.77 bmsfd.pyからの外部ビューア呼び出しにひとまず対応、#totalが読めていなかったのを修正
- 1.78 advanced menu(F7)、ほとんどのモジュールをフォルダ分け
- 1.79 長尺wav（1分以上の1本wav等）の再生を若干改善、画面描画オフセット(note_display_offset_ms)設定追加(オーディオバッファが大きい環境向け)
- 1.80 MixWaver Modeの改善
- 1.81 MixWaver Modeの改善（特にギミック譜面） (bpm>basebpm*100 or bpm>10000で振る舞いが変わるようにしました)、bmsfd.pyの操作性改善(pgdn/pgup/home/end)
