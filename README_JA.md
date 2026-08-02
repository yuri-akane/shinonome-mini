# Shinonome Mini – A minimal console BMS player

Python で実装された、ターミナル上で動作するシンプルな BMS プレイヤーです。
- `curses` による軽量 UI
- 音声は **miniaudio**（純粋 Python ライブラリ）で再生

## 主な機能
- **bms / bmson対応**
- **SP(7keys), DP(14keys)対応**
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

## Notes & Caveats
- UIはterminalだけです。グラフィカルUIはありません。
- 一部の BMS コマンドのみ対応。BMP, BGA 等はスキップします。
- **SCROLL** コマンドは未対応です。今後実装予定です。
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
- デフォルトの文字コードにはshift-jis(cp932), euc-kr(cp949), utf-8を設定できます。

## ライセンス
- GPLv3

## 謝辞
- こちらのプロジェクト [shinonome](https://github.com/kuroclef/shinonome) の作者様に感謝を申し上げます。
- 全く別物になっていますが、基本コンセプトをお借りしているので‑miniとさせていただきました。

## いままでやった & あとでやる
- 基本的なbms再生(BPM変更、小節長変更、STOP、ロングノート、etc) -> ver1.50
- SCROLL命令
- 多重再生の改善（do not playback many-time with single #WAVxx definition）
   - bmsonではpolyphonyに該当する仕様 ->1.53a ok
- BASE命令（36,62） ->1.53a ok
- flac対応 ->1.56 ok?
- pynput use or nouse flag by setting　->1.53b ok
- 画面表示オプション（none(画面なし)、tiny(ノーツのみ、表示幅・高さも縮小)、mini（通常））、コマンドラインオプション
- bmsのデフォルトエンコーディング指定(shift-jis, euc-kr, utf-8) ->1.58 ok
- numpy(cpu負荷軽減) ->1.57c ok

## minimalに保つためやらない
- 画像・動画表示
- hidden/sudden
- スコア記録・保存・送信、ファイル出力
- IR等オンライン接続
- プレイリスト -> ※別のプログラムであとでやる
- #RANDOM〜#IF命令 -> 余裕ができたらやるかも？
- 地雷ノーツ -> 余裕ができたらやるかも？
- ZZ（即死）地雷、不可視ノーツ、FREEZONE
- midi対応
- mp3は再生できますが音ズレがあるのでおすすめしません
- preview
- pms, 774, gda形式 ->やるなら5keys/10keysが先, その後9keys, 4k, 6kまで
- ロングノートは見た目だけです（キーを離した判定ができないため）。
   - 押しっぱなしにすると次のノートでBADをとられる場合があるので少し早めに離してください。

## todoあとで確認
- bmsonのときbpm確認（1ずれない？）
- bmsonのとき実質無音ノーツになってる？
- global変数使うな
