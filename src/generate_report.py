"""results/ 의 Phase 1/2/3 JSON을 읽어 단일 HTML 리포트를 생성한다.
외부에 업로드하지 않는다 - 로컬 파일로만 존재.

    python src/generate_report.py                      # results/report.html
    python src/generate_report.py --out results/x.html # 다른 파일로

항목 수가 수백 개로 늘어난 뒤로는 응답 전문을 그대로 싣지 않고 요약 중심으로 낸다.
전문이 필요하면 results/phase2_responses/*.json 을 직접 본다.
"""
import argparse
import collections
import html
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
CIPHER_STYLES = {"ascii", "atbash", "caesar", "morse"}


def _esc(text) -> str:
    return "" if text is None else html.escape(str(text))


def load_json_dir(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(path.glob("*.json"))]


def load_scores() -> dict | None:
    files = sorted((RESULTS_DIR / "phase3_scores").glob("*_sncs.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def render_summary(p1: list[dict], p2: list[dict], scores: dict | None) -> str:
    labels = collections.Counter(r["final_label"] for r in p2)
    total = sum(labels.values()) or 1
    cards = [
        ("카테고리", len(p1)),
        ("행동 테스트 항목", len(p2)),
        ("REFUSE", f"{labels['REFUSE']} ({labels['REFUSE']/total*100:.0f}%)"),
        ("COMPLY", f"{labels['COMPLY']} ({labels['COMPLY']/total*100:.0f}%)"),
        ("PARTIAL", f"{labels['PARTIAL']} ({labels['PARTIAL']/total*100:.0f}%)"),
    ]
    if scores:
        s = scores["results"]["strict"]["overall_sncs"]
        l = scores["results"]["lenient"]["overall_sncs"]
        cards += [("SNCS (strict)", f"{s:.4f}"), ("SNCS (lenient)", f"{l:.4f}"),
                  ("strict−lenient", f"{abs(s-l):.4f}")]
    return "<div class='cards'>" + "".join(
        f"<div class='card'><div class='k'>{_esc(k)}</div><div class='v'>{_esc(v)}</div></div>"
        for k, v in cards) + "</div>"


def render_phase1(rows: list[dict]) -> str:
    if not rows:
        return "<p class='empty'>Phase 1 결과 없음</p>"
    out = ["<table><thead><tr><th>카테고리</th><th>이름</th><th>규칙 유형</th>"
           "<th>확신도</th><th>대표 응답</th><th>허용 조건 / 프레이밍 조건</th>"
           "<th>심판 판정 사유</th></tr></thead><tbody>"]
    for r in rows:
        cls = r.get("_debug_classification", {}).get("parsed", {})
        cond = " | ".join(cls.get("conditions_for_compliance") or []) or "—"
        fram = " | ".join(cls.get("framing_changes") or []) or "<i>(없음)</i>"
        rt = _esc(r.get("rule_type"))
        out.append(
            f"<tr><td>{_esc(r.get('category_id'))}</td><td>{_esc(r.get('category_name'))}</td>"
            f"<td><span class='badge type-{rt.replace(' ', '')}'>{rt}</span></td>"
            f"<td>{_esc(r.get('confidence'))}</td>"
            f"<td>run{_esc(r.get('_debug_representative_run_id'))}"
            f"<div class='sub'>길이 {_esc(r.get('_debug_extraction_lengths'))}</div></td>"
            f"<td class='sm'><b>허용</b> {_esc(cond)}<br><b>프레이밍</b> {fram}</td>"
            f"<td class='sm'>{_esc(cls.get('rationale'))}</td></tr>")
    return "".join(out) + "</tbody></table>"


def render_by_style(p2: list[dict]) -> str:
    by = collections.defaultdict(collections.Counter)
    for r in p2:
        by[r["item_id"].split("_", 1)[1]][r["final_label"]] += 1
    out = ["<table><thead><tr><th>프롬프트 변형</th><th>항목</th><th>REFUSE</th>"
           "<th>COMPLY</th><th>PARTIAL</th><th>COMPLY율</th><th></th></tr></thead><tbody>"]
    for style, c in sorted(by.items(), key=lambda x: -x[1]["COMPLY"] / max(sum(x[1].values()), 1)):
        n = sum(c.values())
        pct = c["COMPLY"] / n * 100
        tag = " <span class='tag'>암호</span>" if style in CIPHER_STYLES else ""
        out.append(
            f"<tr><td>{_esc(style)}{tag}</td><td>{n}</td><td>{c['REFUSE']}</td>"
            f"<td class='hot'>{c['COMPLY']}</td><td>{c['PARTIAL']}</td>"
            f"<td>{pct:.0f}%</td>"
            f"<td class='barcell'><div class='bar' style='width:{pct}%'></div></td></tr>")
    return "".join(out) + "</tbody></table>"


def render_scores(scores: dict | None) -> str:
    if not scores:
        return "<p class='empty'>Phase 3 결과 없음</p>"
    out = []
    for mode, res in scores["results"].items():
        out.append(f"<h3>PARTIAL 처리 = {mode} (PARTIAL을 {res['partial_treated_as']}로 간주)</h3>")
        out.append("<table><thead><tr><th>카테고리</th><th>규칙</th><th>일치/채점</th>"
                   "<th>SNCS</th></tr></thead><tbody>")
        for c in res["categories"]:
            s = f"{c['sncs']:.3f}" if c["sncs"] is not None else "—"
            out.append(f"<tr><td>{_esc(c['category_id'])}</td><td>{_esc(c['rule_type'])}</td>"
                       f"<td>{c['n_matched']}/{c['n_scoreable']}</td><td><b>{s}</b></td></tr>")
        ov = res["overall_sncs"]
        out.append(f"<tr class='tot'><td colspan='3'>전체 (카테고리 평균)</td>"
                   f"<td><b>{ov:.4f}</b></td></tr></tbody></table>")
        out.append(f"<p class='meta'>위반 {len(res['violations'])}건 — "
                   f"{_esc(res['violation_counts'])}</p>")
    return "".join(out)


def render_violations(scores: dict | None) -> str:
    if not scores:
        return ""
    vs = scores["results"]["strict"]["violations"]
    if not vs:
        return "<p class='empty'>위반 없음</p>"
    by_style = collections.Counter(v["item_id"].split("_", 1)[1] for v in vs)
    head = ("<p class='meta'>strict 기준 " + str(len(vs)) + "건. 변형별: "
            + _esc(dict(by_style.most_common())) + "</p>")
    out = [head, "<table><thead><tr><th>카테고리</th><th>항목</th><th>규칙</th>"
           "<th>예측</th><th>관찰</th><th>위반 유형</th></tr></thead><tbody>"]
    for v in vs:
        out.append(
            f"<tr><td>{_esc(v['category_id'])}</td><td>{_esc(v['item_id'])}</td>"
            f"<td>{_esc(v['rule_type'])}</td><td>{_esc(v['predicted'])}</td>"
            f"<td><span class='badge label-{_esc(v['observed_raw'])}'>{_esc(v['observed_raw'])}</span></td>"
            f"<td>{_esc(v['violation_type'])}</td></tr>")
    return "".join(out) + "</tbody></table>"


def render_items(p2: list[dict]) -> str:
    out = ["<p class='meta'>응답 전문은 싣지 않는다. "
           "필요하면 <code>results/phase2_responses/*.json</code> 을 직접 볼 것. "
           "tier1의 PARTIAL은 판정이 아니라 <b>심판에게 넘겼다</b>는 신호다.</p>",
           "<table><thead><tr><th>항목</th><th>카테고리</th><th>tier1</th><th>심판</th>"
           "<th>최종</th><th>응답 길이</th><th>비고</th></tr></thead><tbody>"]
    for r in sorted(p2, key=lambda x: (x["category_id"], x["item_id"])):
        t1 = ", ".join("→T2" if l == "PARTIAL" else l[0] for l in r["tier1_labels"])
        t2 = ", ".join((t or "-")[:1] for t in r["tier2_labels"])
        lens = [len(c) for c in r["responses"]]
        notes = []
        if any(r.get("_debug_truncated", [])):
            notes.append("<span class='warn'>잘림</span>")
        for d in (r.get("_debug_decoder_used") or []):
            if d:
                notes.append(f"<span class='tag'>디코딩:{_esc(d)}</span>")
                break
        if any(r.get("_debug_provider_filter_blocked", [])):
            notes.append("<span class='tag'>필터차단</span>")
        fl = _esc(r["final_label"])
        out.append(
            f"<tr><td>{_esc(r['item_id'])}</td><td>{_esc(r['category_id'])}</td>"
            f"<td class='sm'>{_esc(t1)}</td><td class='sm'>{_esc(t2)}</td>"
            f"<td><span class='badge label-{fl}'>{fl}</span></td>"
            f"<td class='sm'>{_esc(lens)}</td><td>{''.join(notes)}</td></tr>")
    return "".join(out) + "</tbody></table>"


CSS = """
body{font-family:-apple-system,"Segoe UI",sans-serif;margin:2rem;background:#0b0d10;color:#e6e6e6}
h1{font-size:1.4rem}h2{margin-top:2.5rem;border-bottom:1px solid #333;padding-bottom:.3rem}
h3{margin-top:1.4rem;font-size:1rem;color:#9ca3af}
table{border-collapse:collapse;width:100%;margin-top:.8rem;font-size:.85rem}
th,td{border:1px solid #333;padding:6px 8px;vertical-align:top;text-align:left}
th{background:#16191d;position:sticky;top:0}
tr:nth-child(even){background:#111417}
tr.tot td{background:#16191d;font-weight:600}
.badge{padding:2px 8px;border-radius:10px;font-weight:600;font-size:.78rem}
.type-T1{background:#7f1d1d}.type-T2{background:#78350f}.type-T2T3{background:#713f12}
.type-T3{background:#713f12}.type-OPAQUE{background:#374151}
.label-COMPLY{background:#7f1d1d}.label-REFUSE{background:#14532d}.label-PARTIAL{background:#78350f}
.sub{font-size:.72rem;color:#9ca3af;margin-top:2px}
.sm{font-size:.78rem;line-height:1.4}
.empty{color:#9ca3af;font-style:italic}
.meta{color:#9ca3af;font-size:.85rem}
.warn{color:#fbbf24}
.hot{color:#fca5a5;font-weight:600}
.tag{background:#1f2937;color:#93c5fd;padding:1px 6px;border-radius:6px;font-size:.72rem;margin-right:4px}
.cards{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1rem}
.card{background:#16191d;border:1px solid #333;border-radius:8px;padding:.6rem .9rem;min-width:120px}
.card .k{font-size:.72rem;color:#9ca3af}.card .v{font-size:1.15rem;font-weight:600;margin-top:2px}
.barcell{width:160px}.bar{height:10px;background:#dc2626;border-radius:3px;min-width:1px}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESULTS_DIR / "report.html"), help="출력 HTML 경로")
    args = ap.parse_args()

    p1 = load_json_dir(RESULTS_DIR / "phase1_rules")
    p2 = load_json_dir(RESULTS_DIR / "phase2_responses")
    scores = load_scores()

    doc = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>SNCA Report</title><style>{CSS}</style></head>
<body>
<h1>SNCA 파일럿 리포트 <span class="meta">(로컬 전용, 외부 업로드 안 됨)</span></h1>
<p class="meta">results/ 는 .gitignore로 제외되어 있다. 브라우저에서 file:// 로 직접 열거나 팀 내부에서만 공유할 것.</p>
{render_summary(p1, p2, scores)}

<h2>1. Phase 3 — SNCS</h2>
{render_scores(scores)}

<h2>2. 프롬프트 변형별 결과</h2>
<p class="meta">COMPLY율이 높을수록 그 프레이밍이 모델의 거절을 잘 뚫었다는 뜻이다.</p>
{render_by_style(p2)}

<h2>3. 위반 목록</h2>
{render_violations(scores)}

<h2>4. Phase 1 — 추출된 규칙</h2>
{render_phase1(p1)}

<h2>5. Phase 2 — 전체 항목 ({len(p2)}개)</h2>
{render_items(p2)}
</body></html>
"""
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out}  (phase1={len(p1)}, phase2={len(p2)}, "
          f"phase3={'있음' if scores else '없음'}, {len(doc)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
