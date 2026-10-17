#!/usr/bin/env bash
# shinonome-mini プレイリスト再生スクリプト (ランダム再生)
# 指定ディレクトリ配下のBMS/BMSONファイルを検索してランダム順に再生します。
# ※ 各フォルダから1曲のみを再生します。

echo "[Ctrl+C]x2 Quit player"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET_DIR="$(cd "${1:-.}" && pwd)"

# 1. BMSファイルを検索・ソートし、フォルダごとに1ファイル抽出したのちシャッフル
# 2. fd 3 経由で1曲ずつ再生 (Enterでのスキップに対応するため </dev/tty を指定)
exec 3< <(find "${TARGET_DIR}" -type f \( -iname "*.bms" -o -iname "*.bme" -o -iname "*.bml" -o -iname "*.pms" -o -iname "*.bmson" \) \
    | sort \
    | awk -F'/' '{
        dir="";
        for (i=1; i<NF; i++) {
            dir = (i==1 ? $i : dir "/" $i);
        }
        if (!seen[dir]++) {
            print $0;
        }
    }' \
    | shuf)

while IFS= read -r fname <&3; do
    echo "----------------------------------------"
    echo "Playing (Random): ${fname}"
    python3 "${BASE_DIR}/cnnm.py" "${fname}" --soundonly </dev/tty 2> /dev/null
done

exec 3<&-
