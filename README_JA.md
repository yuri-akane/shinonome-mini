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
- **Esc** キーで終了します。
- キー設定は `settings.toml` で自由に変更可能です（デフォルトは `z s x d …` など）。
- consoleなのでshiftキー押下が判別できず、そのためスクラッチはデフォルトでa,tab,spaceに割り当てています（変更可能です）。
- 表示がおかしかったらterminalをfullscreenにしてください

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## Notes & Caveats
- UI は端末だけの表示で、グラフィカル UI はありません。
- 現在は一部 BMS コマンドのみ対応。BMP,BGA 等はスキップします。
- **BPM 変更** と **小節長変更** に対応しました。
- **STOP**、**SCROLL** コマンドは未対応です。今後実装予定です。
- `settings.toml` では **Shift / Ctrl / Alt** キーは割り当てできません。
- Shift‑JIS エンコードの BMS ファイルでの動作を想定しています。
- bmson 形式はまだ未対応です。

## ライセンス
- GPLv3

## 謝辞
- こちらのプロジェクト [shinonome](https://github.com/kuroclef/shinonome) の作者様にこの場を借りて感謝を申し上げます。
- 全く別物になっていますが、基本コンセプトをお借りしているので-miniとさせていただきました。

## あとでやる
- スクラッチがrightかつrandomつけたときenbugしているのでdebug
- bmson
- ロングノート
- STOP、SCROLL
- global変数使うな
- debuglogファイル出力の扱い（リリースでは消すように工夫します）

## minimalに保つためやらない
- 画像・動画表示
- HS(hispeed) -> 簡単そうなのでやるかも
- hidden/sudden
- スコア記録・保存・送信。ファイル出力・オンライン接続。
- プレイリスト -> ※別のプログラムであとでやる
- 地雷ノーツ
- #RANDOM〜#IF命令
