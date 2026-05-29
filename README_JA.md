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

## 必要環境
- Python 3.10 以上
- ALSA / PulseAudio 等、`miniaudio` が利用できるオーディオ環境

## セットアップ手順

```bash
# 1. 仮想環境作成
python3-m venv venv

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
- **Esc** キーで終了します。
- キー設定は `settings.toml` で自由に変更可能です（デフォルトは `z s x d …` など）。
- 表示がおかしかったらterminalをfullscreenにしてください

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## Notes & Caveats
- The UI is terminal‑only; no graphical interface.
- Only a subset of BMS commands are currently parsed. BMP (`01`) is kept for BGM, while background layers (BGA) and other visual commands are skipped.
- STOP and BPM‑change commands are marked for future implementation.
- Works best on Shift‑JIS encoded BMS files.

## ライセンス
- GPLv3

## 謝辞
- 参考とさせていただいた Shinonome の作者様に感謝を。
