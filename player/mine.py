# 地雷ノーツ関連のヘルパー関数

def decode_mine_damage(obj: str) -> float:
    """BMS地雷ノーツのダメージ値をデコードする。
    obj: BMS base-36 の2文字文字列（例: "1A" → 46/2 = 23.0%）
    戻り値: ゲージ減少量（%）
    """
    try:
        value = int(obj, 36)
    except Exception:
        return 0.0
    return value / 2.0


def decode_mine_damage_numeric(damage) -> float:
    """bmson mine_channels のダメージ値をデコードする。
    damage: bmson の damage フィールド（数値、既に%単位）
    戻り値: ゲージ減少量（%）
    """
    try:
        return float(damage)
    except Exception:
        return 0.0


def is_mine_channel(channel: str) -> bool:
    """地雷ノーツのチャンネルか判定する。
    Mine channels are D1-D9 (1P) and E1-E9 (2P).
    """
    if not isinstance(channel, str):
        return False

    ch = channel.strip().upper()

    if len(ch) >= 2:
        prefix = ch[0]
        suffix = ch[1:]
        if prefix in ('D', 'E') and suffix.isdigit():
            try:
                num = int(suffix)
                return 1 <= num <= 9
            except ValueError:
                return False

    return False
