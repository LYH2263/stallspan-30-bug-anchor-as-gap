from app.services.first_fit_engine import (
    REASON_ANCHOR_MISMATCH,
    REASON_NO_SPAN,
    allocate_first_fit,
    feasible_start_window,
    free_spans_from_pillars,
)

PILLARS = [
    {"position_m": 10.0, "thickness_m": 0.5},
    {"position_m": 20.0, "thickness_m": 0.5},
]


def _by_name(result, name):
    return next((p for p in result.placements if p.vendor_name == name), None)


def _rejected(result, name):
    return next((r for r in result.rejected if r.vendor_name == name), None)


def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, PILLARS)
    assert len(spans) == 3
    assert spans[0][0] == 0.0
    # 柱体按半厚阻断
    assert spans[0][1] == 9.75
    assert spans[1] == (10.25, 19.75)


def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert any(p.vendor_name == "A" for p in r.placements)
    assert len(r.placements) + len(r.rejected) == 2


def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    assert len(r.rejected) == 1
    assert r.rejected[0].vendor_name == "Huge"
    assert r.rejected[0].reason == REASON_NO_SPAN


# ---------- 锚点落位 ----------

def test_seed_linji_anchor_lands_in_band_and_does_not_cross_pillar():
    """种子场景：林记糖水 11±1，起点必须落在 10～12 且不跨柱。"""
    vendors = [
        {"id": 1, "name": "阿强烧烤", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "林记糖水", "stall_width_m": 3.0, "priority": 1,
         "anchor_m": 11.0, "anchor_tolerance_m": 1.0},
        {"id": 3, "name": "大碗面", "stall_width_m": 6.0, "priority": 1},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    lin = _by_name(r, "林记糖水")
    assert lin is not None, "林记糖水应当成功落位"
    # 起点落在容差带 10～12
    assert 10.0 <= lin.start_m <= 12.0
    # 不跨柱：柱A 占据 [9.75,10.25]，起点须在柱右缘之外，终点在柱B 左缘之内
    assert lin.start_m >= 10.25
    assert lin.end_m <= 19.75


def test_width_fits_but_start_out_of_band_is_anchor_mismatch():
    """空档宽度够，但起点必越出容差带 → 锚点不符，不得写成空档不足，且图上无此块。"""
    vendors = [
        # 唯一空档 [0,10]，宽 3 放得下；锚点 9±0.5 → 起点带 [8.5,9.5]，
        # 可放起点段为 [0,7]，交集为空。
        {"id": 1, "name": "偏锚点", "stall_width_m": 3.0, "priority": 1,
         "anchor_m": 9.0, "anchor_tolerance_m": 0.5},
    ]
    # 用一根很靠右的柱把可用区间限制在 [0,10]：柱在 20，空档 [0,19.75]/[20.25,30]
    # 这里改用宽度 10、无柱的街段，得到单一空档 [0,10]。
    r = allocate_first_fit(10.0, vendors, pillars=[])
    rej = _rejected(r, "偏锚点")
    assert rej is not None
    assert rej.reason == REASON_ANCHOR_MISMATCH
    assert _by_name(r, "偏锚点") is None  # 图上不得画出越界色块
    # 容差带仍提供给前端
    assert any(b["vendor_id"] == 1 for b in r.anchor_bands)


def test_anchor_skips_span_and_finds_later_one():
    """第一个空档宽度够但起点越界，跳过它，在后续空档落位。"""
    vendors = [
        # 锚点 15±0.5 → 起点带 [14.5,15.5]
        {"id": 1, "name": "跨档找位", "stall_width_m": 3.0, "priority": 1,
         "anchor_m": 15.0, "anchor_tolerance_m": 0.5},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p = _by_name(r, "跨档找位")
    assert p is not None
    # 第一空档 [0,9.75] 放不下起点带 → 跳过；落入第二空档 [10.25,19.75]
    assert 14.5 <= p.start_m <= 15.5
    assert p.start_m >= 10.25 and p.end_m <= 19.75


def test_no_anchor_still_left_packed():
    """无锚点摊仍从左填，起点即空档左缘。"""
    vendors = [{"id": 1, "name": "普通摊", "stall_width_m": 4.0, "priority": 1}]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    p = _by_name(r, "普通摊")
    assert p.start_m == 0.0
    assert p.anchor_m is None


def test_anchor_mid_span_keeps_left_remainder():
    """锚点摊落在空档中部后，左侧残段仍可被后来的摊填用。"""
    vendors = [
        {"id": 1, "name": "锚点摊", "stall_width_m": 2.0, "priority": 1,
         "anchor_m": 11.0, "anchor_tolerance_m": 1.0},  # 起点 10.25，占 [10.25,12.25]
        {"id": 2, "name": "填左缝", "stall_width_m": 3.0, "priority": 2},
    ]
    r = allocate_first_fit(30.0, vendors, PILLARS)
    anchor = _by_name(r, "锚点摊")
    filler = _by_name(r, "填左缝")
    assert anchor is not None and filler is not None
    # 填空档从最左开始：第一空档 [0,9.75]
    assert filler.start_m == 0.0


def test_feasible_window_same_source_for_fit_and_reject():
    """同一判定函数：宽度够+带内给窗口；越界给 None；宽度不够也给 None。"""
    # 空档 [10.25,19.75]，need 3，锚点 11±1
    win = feasible_start_window([10.25, 19.75], 3.0, 11.0, 1.0)
    assert win is not None
    lo, hi = win
    assert lo >= 10.25 and hi <= 12.0
    # 宽度不够
    assert feasible_start_window([0.0, 2.0], 3.0, 1.0, 1.0) is None
    # 宽度够但起点越界
    assert feasible_start_window([0.0, 10.0], 3.0, 9.0, 0.5) is None
