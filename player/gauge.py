
#gauge関係は将来的にすべてこのモジュールに移動する

def _hard_gauge_loss(gauge, is_miss: bool) -> float:
    """HARDゲージのBAD/MISS時ゲージ減少量を計算する（負の値を返す）。
    現在のゲージ量 x = gauge/100 に応じた補正関数を使用する。
      f(x) = 1 - (1-x)^2
      BAD : -(1 + 4*f(x))
      MISS: -(2 + 8*f(x))
    ゲージが高いほど減少量が大きく、低いほど減少量が小さい。
    """
    x = gauge / 100.0
    fx = 1.0 - (1.0 - x) ** 2
    if is_miss:
        return -(2.0 + 8.0 * fx)
    else:
        return -(1.0 + 4.0 * fx)

def _solid_gauge_gain_factor(gauge) -> float:
    """SOLIDゲージのゲージ増加量のgain_factorを計算する。
    現在のゲージ量 x = gauge/100 に応じた補正関数を使用する。
      f(x) = (1-x^2)/1.5
    ゲージが高いほど増加量が小さく、低いほど増加量が大きい。いずれの場合でも通常ゲージよりは小さい。
    ゲージ増加量（比）：{0%: 2/3, 50%: 1/2, 70%: 1/3, 80%: 1/4, 90%: 1/8, 95%: 1/16, 99%: 1/75}
    """
    # SOLIDゲージ: ゲージに応じて回復量を抑制、イージーでもハードでも適用される
    x = gauge / 100.0
    return (1.0 - x ** 2) / 1.5

def _set_gauge_loss_factor(easy_mode, solid_gauge):
    """通常/easyゲージのBAD/MISS時ゲージ減少量のloss_factorを計算する。
    イージーモード時はゲージ減少量を1/2にする。
    solidゲージの場合は1/3にする。(easy併用なら1/6)
    """
    x = 1.0
    if easy_mode:
        x /= 2.0
    if solid_gauge:
        x /= 3.0
    return x

def _reset_gauge(solid_gauge, hard_mode):
    """optionに応じたゲージリセット"""
    if solid_gauge: #solid+hardでも60%始まり
        return 60.0
    elif hard_mode:
        return 100.0
    else:
        return 22.0

def set_gauge_increment(inc, hard_mode):
    # モード別のゲージ増加倍率を決定
    # solid_gaugeは現在のgauge依存なので別に定義する
    if hard_mode:
        # HARDゲージ: 回復量を抑制
        return inc * 0.2, inc * 0.15, inc * 0.1
    else:
        # easyゲージと通常ゲージ: 通常の回復量
        return inc, inc, inc * 0.5
