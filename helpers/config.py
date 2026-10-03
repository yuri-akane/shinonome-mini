# -------------------------------------------------
# ファイル名・表記揺れ吸収用 Unicode 互換文字グループの定義
# -------------------------------------------------
CHAR_EQUIVALENCE_GROUPS = [
    {'\u301c', '\uff5e'},  # Wave dash (〜) vs Fullwidth tilde (～)
    {'\u2014', '\u2015'},  # Em dash (—) vs Horizontal bar (―)
    {'\u2212', '\uff0d'},  # Minus sign (−) vs Fullwidth hyphen-minus (－)
]

# 各グループ内の先頭要素（Unicode順ソート時の先頭）を代表文字に採用する
_NORMALIZE_MAP = {
    c: sorted(list(group))[0]
    for group in CHAR_EQUIVALENCE_GROUPS
    for c in group
}

def normalize_filename_chars(text: str) -> str:
    """互換文字グループに含まれる文字を統一された代表文字に正規化する。"""
    return "".join(_NORMALIZE_MAP.get(ch, ch) for ch in text)

def get_filename_variants(text: str) -> list[str]:
    """
    文字列中の互換文字（波ダッシュ、ダッシュ記号、マイナス記号等）について、
    考えられるすべての表記バリエーションのリストを返す。
    重複を除外した順序保存リスト。
    """
    variants = [text]
    for group in CHAR_EQUIVALENCE_GROUPS:
        new_variants = []
        for v in variants:
            found_chars = [ch for ch in group if ch in v]
            if not found_chars:
                if v not in new_variants:
                    new_variants.append(v)
                continue

            for src_char in found_chars:
                for target_char in group:
                    if src_char == target_char:
                        if v not in new_variants:
                            new_variants.append(v)
                    else:
                        replaced = v.replace(src_char, target_char)
                        if replaced not in new_variants:
                            new_variants.append(replaced)
        variants = new_variants
    return variants
