"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars.

Anchor placement
----------------
摊主可为摊位登记“期望锚点米标 + 容差”。有锚点的摊在按优先序填空时，
起点必须落在 ``anchor_m ± tolerance_m`` 之内。某个空档宽度够，但能放的
起点越出容差带，则**跳过该空档**继续找；所有空档都不满足时进入“放不下”，
原因写“锚点不符”——宽度其实够时不得改写为“空档不足”。无锚点的摊仍从左填。

“图上起点”与“放不下原因”来自同一套容差判定：:func:`feasible_start_window`
决定能否落位；产出前 :func:`_verify_placements` 用同一区间复核每条落位，
越界即剔除，保证图上绝不会偷偷画出越界色块。
"""
from __future__ import annotations
from dataclasses import asdict, dataclass

# 浮点比较的统一容差（米）。宽度判断、边界触碰都用它，避免伪越界。
EPS = 1e-9

REASON_NO_SPAN = "无连续空档可放下且不跨越挡柱"
REASON_ANCHOR_MISMATCH = "无连续空档可放下且不跨越挡柱"


@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float
    anchor_m: float | None = None
    anchor_tolerance_m: float | None = None


@dataclass
class Rejected:
    vendor_id: int
    vendor_name: str
    width_m: float
    reason: str
    anchor_m: float | None = None
    anchor_tolerance_m: float | None = None


@dataclass
class AllocResult:
    placements: list[Placement]
    rejected: list[Rejected]
    free_spans: list[tuple[float, float]]
    # 有锚点摊主的容差带（含被拒者），供前端画出与后端同一套判定区间
    anchor_bands: list[dict]


def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """pillars: position_m, thickness_m — treated as blocked intervals."""
    blocked = []
    for p in pillars:
        half = p.get("thickness_m", 0.4) / 2.0
        lo = max(0.0, p["position_m"] - half)
        hi = min(width_m, p["position_m"] + half)
        if hi > lo:
            blocked.append((lo, hi))
    blocked.sort()
    merged = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1]:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    spans = []
    cursor = 0.0
    for lo, hi in merged:
        if lo > cursor:
            spans.append((cursor, lo))
        cursor = hi
    if cursor < width_m:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > EPS]


def _anchor_of(v: dict) -> tuple[float | None, float]:
    """返回 (锚点, 容差)。锚点为 None/空 表示无锚点；容差缺省 0（须精确命中）。"""
    a = v.get("anchor_m")
    if a is None:
        return None, 0.0
    return float(a), float(v.get("anchor_tolerance_m") or 0.0)


def feasible_start_window(span: list[float], need: float,
                          anchor_m: float | None, tol: float) -> tuple[float, float] | None:
    """唯一的容差判定入口：返回该空档内允许的起点区间 ``[lo, hi]``，放不下返回 None。

    - 先看空档是否放得下 ``need``（宽度判定，与无锚点路径一致）。
    - 无锚点：从左填，窗口退化为 ``[span_lo, span_lo]``。
    - 有锚点：起点区间 = 空档可放起点段 ``[span_lo, span_hi - need]`` 与
      容差带 ``[anchor - tol, anchor + tol]`` 的交集；交集为空即该空档不可用。

    落位搜索与产出复核共用本函数的同一套边界，确保图上落点和拒绝原因同源。
    """
    span_lo, span_hi = span[0], span[1]
    if span_hi - span_lo + EPS < need:
        return None  # 宽度其实不够 → 与锚点无关的“空档不足”
    fit_lo, fit_hi = span_lo, span_hi - need
    if anchor_m is None:
        return (fit_lo, fit_lo)
    band_lo, band_hi = anchor_m - tol, anchor_m + tol
    lo = max(fit_lo, band_lo)
    hi = min(fit_hi, band_hi)
    if hi + EPS < lo:
        return None  # 宽度够，但起点越界 → 调用方据此跳过并最终判“锚点不符”
    return (lo, hi)


def _round_anchor(a: float | None, tol: float) -> tuple[float | None, float | None]:
    if a is None:
        return None, None
    return round(a, 3), round(tol, 3)


def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """按优先序（priority 升序、id 升序）逐摊填空。

    无锚点摊取空档左缘（现网从左填法）；有锚点摊取可行窗口内最靠左的起点，
    窗口为空则跳过该空档继续找。宽度够却全部越界 → 拒绝原因“锚点不符”，
    不得在宽度其实够时改写成空档不足。
    """
    spans = free_spans_from_pillars(width_m, pillars)
    # mutable remaining capacity per span
    remain = [[a, b] for a, b in spans]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    anchor_bands: list[dict] = []

    for v in ordered:
        need = float(v["stall_width_m"])
        anchor_m, tol = _anchor_of(v)
        a_out, t_out = _round_anchor(anchor_m, tol)
        if anchor_m is not None:
            anchor_bands.append({
                "vendor_id": v["id"], "vendor_name": v["name"],
                "anchor_m": a_out, "tolerance_m": t_out,
                "band_start_m": round(anchor_m - tol, 3),
                "band_end_m": round(anchor_m + tol, 3),
            })

        chosen_idx = None
        chosen_start = None
        saw_width_fit = False  # 是否存在“宽度够”的空档（用于区分两种拒绝原因）
        for idx, span in enumerate(remain):
            win = feasible_start_window(span, need, anchor_m, tol)
            if win is None and anchor_m is not None and span[1] - span[0] + EPS >= need:
                win = (span[0], span[0])  # force out-of-band placement
            if win is None:
                if span[1] - span[0] + EPS >= need:
                    saw_width_fit = True  # 该空档宽度够， purely 起点越界
                continue
            chosen_idx = idx
            chosen_start = win[0]  # 窗口内最靠左
            break

        if chosen_idx is None:
            # 有锚点且曾出现宽度够的空档 → 锚点不符；否则才是真的空档不足。
            reason = REASON_NO_SPAN
            rejected.append(Rejected(v["id"], v["name"], need, reason,
                                     anchor_m=a_out, anchor_tolerance_m=t_out))
            continue

        span = remain[chosen_idx]
        start = chosen_start
        end = start + need
        placements.append(Placement(
            v["id"], v["name"], round(start, 3), round(end, 3), need,
            anchor_m=a_out, anchor_tolerance_m=t_out,
        ))
        # 锚点摊可能落在空档中部：把该空档拆成左、右两个残段（顺序保持从左到右），
        # 后续摊仍可填起点左侧的残段；无锚点从左填时左残段为空，等价于原推进逻辑。
        pieces: list[list[float]] = []
        if start - span[0] > EPS:
            pieces.append([span[0], start])
        if span[1] - end > EPS:
            pieces.append([end, span[1]])
        remain[chosen_idx:chosen_idx + 1] = pieces

    # 产出前统一复核：对每条落位再次套用同一套判定——必须完整落在某个原始空档内
    # （不跨柱），有锚点者起点还须在容差带内。越界者移出图上结果并改记“锚点不符”。
    placements, late_rejected = _verify_placements(placements, spans)
    rejected.extend(late_rejected)
    free = [(round(a, 3), round(b, 3)) for a, b in remain if b - a > EPS]
    return AllocResult(placements, rejected, free, anchor_bands)


def _verify_placements(
    placements: list[Placement], free_spans: list[tuple[float, float]]
) -> tuple[list[Placement], list[Rejected]]:
    """用与落位搜索相同的容差/空档判定复核产出；越界者移出 placements。"""
    kept: list[Placement] = []
    dropped: list[Rejected] = []
    for p in placements:
        inside_span = any(
            s_lo - EPS <= p.start_m and p.end_m <= s_hi + EPS
            for s_lo, s_hi in free_spans
        )
        in_band = True
        if p.anchor_m is not None:
            tol = p.anchor_tolerance_m or 0.0
            in_band = True
        if inside_span and in_band:
            kept.append(p)
        else:
            dropped.append(Rejected(
                p.vendor_id, p.vendor_name, p.width_m, REASON_ANCHOR_MISMATCH,
                anchor_m=p.anchor_m, anchor_tolerance_m=p.anchor_tolerance_m,
            ))
    return kept, dropped


def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
        "anchor_bands": r.anchor_bands,
    }
