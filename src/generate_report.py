"""results/phase1_rules, results/phase2_responses의 JSON을 읽어
로컬에서 바로 열어볼 수 있는 단일 HTML 리포트(results/report.html)를 생성한다.
외부에 업로드하지 않는다 - 로컬 파일로만 존재.
"""
import html
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def _esc(text) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def load_json_dir(path: Path) -> list[dict]:
    items = []
    if not path.exists():
        return items
    for f in sorted(path.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            items.append(json.load(fh))
    return items


def render_phase1_table(rows: list[dict]) -> str:
    if not rows:
        return "<p class='empty'>Phase 1 결과 없음</p>"
    parts = ["<table><thead><tr>",
              "<th>category_id</th><th>category_name</th><th>rule_type</th>",
              "<th>confidence</th><th>Q1~Q5 / rationale</th>",
              "</tr></thead><tbody>"]
    for r in rows:
        qa = (
            f"<b>Q1</b> {_esc(r.get('q1_default'))[:200]}<br>"
            f"<b>Q2</b> {_esc(r.get('q2_refusal_conditions'))[:200]}<br>"
            f"<b>Q3</b> {_esc(r.get('q3_compliance_conditions'))[:200]}<br>"
            f"<b>Q4</b> {_esc(r.get('q4_framing_sensitivity'))[:200]}<br>"
            f"<b>Q5</b> {_esc(r.get('q5_policy_statement'))[:200]}<br>"
            f"<i>rationale:</i> {_esc(r.get('rationale'))[:200]}"
        )
        votes = _esc(r.get("_debug_type_votes"))
        parts.append(
            f"<tr><td>{_esc(r.get('category_id'))}</td>"
            f"<td>{_esc(r.get('category_name'))}</td>"
            f"<td><span class='badge type-{_esc(r.get('rule_type')).replace(' ', '')}'>{_esc(r.get('rule_type'))}</span>"
            f"<div class='sub'>votes: {votes}</div></td>"
            f"<td>{_esc(r.get('confidence'))}</td>"
            f"<td class='qa'>{qa}</td></tr>"
        )
    parts.append("</tbody></table>")
    return "".join(parts)


def render_phase2_table(rows: list[dict]) -> str:
    if not rows:
        return "<p class='empty'>Phase 2 결과 없음</p>"
    parts = ["<p class='meta'>tier1_labels의 'ESCALATED→Tier2'는 Tier1이 애매하다고 판단해 "
              "심판 모델(Tier2)에게 넘겼다는 신호일 뿐, 최종 판정이 아닙니다. "
              "실제 REFUSE/COMPLY/PARTIAL 결과는 final_label 컬럼을 보세요.</p>",
              "<table><thead><tr>",
              "<th>item_id</th><th>category_id</th><th>prompt</th>",
              "<th>tier1_labels</th><th>tier2_labels</th><th>final_label</th>",
              "<th>responses</th><th>truncated</th>",
              "</tr></thead><tbody>"]
    for r in rows:
        responses_html = "<hr>".join(
            f"<div class='run'><b>run{i}</b> ({_esc(fr)}): {_esc(resp)[:400]}"
            f"{'...' if len(str(resp)) > 400 else ''}</div>"
            for i, (resp, fr) in enumerate(zip(r.get("responses", []), r.get("_debug_finish_reasons", [])))
        )
        tier2 = r.get("tier2_labels", [None, None, None])
        tier2_html = "<br>".join(_esc(t)[:150] if t else "<i>-</i>" for t in tier2)
        truncated = r.get("_debug_truncated", [])
        trunc_html = "⚠️ YES" if any(truncated) else "no"
        parts.append(
            f"<tr><td>{_esc(r.get('item_id'))}</td>"
            f"<td>{_esc(r.get('category_id'))}</td>"
            f"<td class='prompt'>{_esc(r.get('prompt'))[:300]}</td>"
            f"<td>{', '.join('ESCALATED→Tier2' if l == 'PARTIAL' else _esc(l) for l in r.get('tier1_labels', []))}</td>"
            f"<td class='tier2'>{tier2_html}</td>"
            f"<td><span class='badge label-{_esc(r.get('final_label'))}'>{_esc(r.get('final_label'))}</span></td>"
            f"<td class='responses'>{responses_html}</td>"
            f"<td>{trunc_html}</td></tr>"
        )
    parts.append("</tbody></table>")
    return "".join(parts)


def main():
    phase1_rows = load_json_dir(RESULTS_DIR / "phase1_rules")
    phase2_rows = load_json_dir(RESULTS_DIR / "phase2_responses")

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>SNCA Pilot Report</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; margin: 2rem; background: #0b0d10; color: #e6e6e6; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ margin-top: 2.5rem; border-bottom: 1px solid #333; padding-bottom: .3rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; font-size: 0.85rem; }}
  th, td {{ border: 1px solid #333; padding: 6px 8px; vertical-align: top; text-align: left; }}
  th {{ background: #16191d; position: sticky; top: 0; }}
  tr:nth-child(even) {{ background: #111417; }}
  .badge {{ padding: 2px 8px; border-radius: 10px; font-weight: 600; font-size: 0.78rem; }}
  .type-T1 {{ background: #7f1d1d; }}
  .type-T2 {{ background: #78350f; }}
  .type-T2T3 {{ background: #713f12; }}
  .type-OPAQUE {{ background: #374151; }}
  .label-COMPLY {{ background: #7f1d1d; }}
  .label-REFUSE {{ background: #14532d; }}
  .label-PARTIAL {{ background: #78350f; }}
  .sub {{ font-size: 0.72rem; color: #9ca3af; margin-top: 2px; }}
  .empty {{ color: #9ca3af; font-style: italic; }}
  .prompt {{ max-width: 260px; }}
  .responses {{ max-width: 420px; }}
  .run {{ margin-bottom: 4px; }}
  .qa {{ max-width: 380px; font-size: 0.8rem; line-height: 1.4; }}
  .meta {{ color: #9ca3af; font-size: 0.85rem; }}
  .warn {{ color: #fbbf24; }}
</style>
</head>
<body>
<h1>SNCA Pilot Report (로컬 전용, 외부 업로드 안 됨)</h1>
<p class="meta">이 파일은 로컬에서만 열어보는 용도입니다. results/ 는 .gitignore로 제외되어 있으니
브라우저에서 file:// 경로로 직접 열거나 팀 내부망에서만 공유하세요.</p>

<h2>Phase 1 — 정책 추출 &amp; 분류 ({len(phase1_rows)}개 카테고리)</h2>
{render_phase1_table(phase1_rows)}

<h2>Phase 2 — 행동 테스트 ({len(phase2_rows)}개 항목)</h2>
{render_phase2_table(phase2_rows)}

</body>
</html>
"""
    out_path = RESULTS_DIR / "report.html"
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"wrote {out_path} (phase1={len(phase1_rows)} rows, phase2={len(phase2_rows)} rows)")


if __name__ == "__main__":
    main()
