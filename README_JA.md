# Shinonome Mini – A minimal console BMS player

Python で実装された、ターミナル上で動作するシンプルな BMS プレイヤーです。
- `curses` による軽量 UI
- 音声は **miniaudio**（純粋 Python ライブラリ）で再生

## 主な機能
- **bms / bmson対応**
- **SP(7keys), DP(14keys)対応**
- **AUTO PLAY / MIRROR / RANDOM / EASY** オプションを UI で切替
- `settings.toml` にキー割り当て・設定を外部化
- オフライン、ファイル出力なし

## 必要環境
- Python 3.10 以上
- ALSA / PulseAudio 等、`miniaudio` が利用できるオーディオ環境
- **pynput** – Shift / Ctrl / Alt キー判定のみに使用しています。

## セットアップ手順
```bash
# 1. 仮想環境作成
python3 -m venv venv

# 2. 仮想環境有効化（Linux/macOS）
source venv/bin/activate
# Windows の場合: venv\\Scripts\\activate

# 3. 必要パッケージをインストール
pip3 install miniaudio pynput
```

## 実行例
```bash
python3 main.py path/to/your_chart.bms
```
- **Esc** キーで終了します。（設定で変更可）
- 表示がおかしかったらterminalをfullscreenにしてください。

## Notes & Caveats
- UI は端末だけの表示で、グラフィカル UI はありません。
- 一部の BMS コマンドのみ対応。BMP, BGA 等はスキップします。
- **SCROLL** コマンドは未対応です。今後実装予定です。
- **pynput** で **Shift / Ctrl / Alt** キーの判定に対応しています。
- Wayland 環境では `onrelease` が利用できないため、ロングノートの離した時の判定は未実装（consoleで行う限り実装不可）です。
- キー設定は `settings.toml` で自由に変更可能です（デフォルトは `z s x d …` など）。
- Hispeed 変更ボタンのデフォルト動作を `keyup`/`keydown` に変更しました。設定でカスタマイズ可能です。
- bms 形式はShift‑JIS(cp932)決め打ちで読み込んでいます。昔のeuc-kr(cp949)とかは未確認です…

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## ライセンス
- GPLv3

## 謝辞
- こちらのプロジェクト [shinonome](https://github.com/kuroclef/shinonome) の作者様に感謝を申し上げます。
- 全く別物になっていますが、基本コンセプトをお借りしているので‑miniとさせていただきました。

## あとでやる（ver1.50以降or順次）
- SCROLL命令
- 多重再生の改善（do not playback many-time with single #WAVxx definition）
- BASE命令（36,62）
- flac対応

## minimalに保つためやらない
- 画像・動画表示
- hidden/sudden
- スコア記録・保存・送信、ファイル出力
- IR等オンライン接続
- プレイリスト -> ※別のプログラムであとでやる
- #RANDOM〜#IF命令 -> 余裕ができたらやるかも？
- 地雷ノーツ -> 余裕ができたらやるかも？
- 不可視ノーツ
- mp3, midi対応
- preview
- pms, 774, gda形式 ->やるなら5keys/10keysが先, その後9keys, 4k, 6kまで
- ロングノートは見た目だけです（キーを離した判定ができないため）。
   - 押しっぱなしにすると次のノートでBADをとられる場合があるので少し早めに離してください。

## todoあとで確認
- bmsonのときbpm確認（1ずれない？）
- bmsonのとき実質無音ノーツになってる？
- global変数使うな
