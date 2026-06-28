# Shinonome Mini – A minimal console BMS player

## 概要
Python で実装された、ターミナル上で動作するシンプルな BMS プレイヤーです。
- `curses` による軽量 UI
- 音声は **miniaudio**（純粋 Python ライブラリ）で再生
- BMS と bmson（予定） の両方をパース可能（不要チャンネルはスキップ）

## 主な機能
- **SP,DP対応**
- **AUTO PLAY / MIRROR / RANDOM / EASY** オプションを UI で切替
- `settings.toml` にキー割り当て・設定を外部化
- 曲情報は **タイトル + アーティスト** を同時表示
- オフライン、ファイル出力なし

## 必要環境
- Python 3.10 以上
- ALSA / PulseAudio 等、`miniaudio` が利用できるオーディオ環境

## セットアップ手順

```bash
# 1. 仮想環境作成
python3 -m venv venv

# 2. 仮想環境有効化（Linux/macOS）
source venv/bin/activate
# Windows の場合: venv\Scripts\activate

# 3. 必要パッケージをインストール
pip3 install miniaudio
```

## 実行例

```bash
python3 main.py path/to/your_chart.bms
```

- 起動後はフルスクリーンの curses UI が表示されます。
- **Esc** キーで終了します。(設定で変更可)
- キー設定は `settings.toml` で自由に変更可能です（デフォルトは `z s x d …` など）。
- consoleなのでshiftキー押下が判別できず、そのためスクラッチはデフォルトでa,tab,spaceに割り当てています（変更可能です）。
   - ->future support
- 表示がおかしかったらterminalをfullscreenにしてください

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## Notes & Caveats
- UI は端末だけの表示で、グラフィカル UI はありません。
- 現在は一部 BMS コマンドのみ対応。BMP,BGA 等はスキップします。
- **SCROLL** コマンドは未対応です。今後実装予定です。
- ロングノートの「ボタンを離した時」の動作はまだ対応していません。#LNTYPE 1がまだちょっとbuggyです。今後対応予定です。
- `settings.toml` では **Shift / Ctrl / Alt** キーは割り当てできません。今後対応予定です。
- bms 形式はShift‑JISを想定しています。
- bmson 形式は今後対応予定です。

## ライセンス
- GPLv3

## 謝辞
- こちらのプロジェクト [shinonome](https://github.com/kuroclef/shinonome) の作者様にこの場を借りて感謝を申し上げます。
- 全く別物になっていますが、基本コンセプトをお借りしているので-miniとさせていただきました。

## あとでやる（ver2.0まで）
- bmson対応
- ロングノート対応改善とShift / Ctrl / Altキー対応
   - pynputを使用予定。方式がだいぶ変わってしまうので少したいへん

## あとでやる（ver2.0以降or順次）
- SCROLL命令
- STOP命令改善
   - 一応実装したが、まだsasakure氏のX等の停止時間がおかしい？
- 多重再生の改善
   - #WAVxxに定義されている音は、繰り返し鳴るときは停止してまた再生しなければならない（通常の打楽器と同様）。そうしないとDELAYMASTER等連続して叩いた時に音割れが激しくなる。同じ音声ファイル(*.wav, *.ogg)の繰り返しを途中で停止することなく重ねて鳴らしたいときは#WAVxx, #WAVyyと（音声を）多重定義して交互に配置するテクニックの、再生側の実装。
- global変数使うな
- BASE命令（36,62）
- flac対応

## minimalに保つためやらない
- 画像・動画表示
- hidden/sudden
- スコア記録・保存・送信、ファイル出力（debug用コードはversionによって残っている場合があります）
- IR等オンライン接続
- プレイリスト -> ※別のプログラムであとでやる
- #RANDOM〜#IF命令 ->余裕ができたらやるかも？
- 地雷ノーツ ->余裕ができたらやるかも？
- 不可視ノーツ
- mp3, midi対応
- pms, 774, gda形式 ->pmsくらいはやるかも…？
