"""ReportRender service — render the compliance assessment as a cited report.

Pure function. The rendered report ALWAYS carries the KB version + as-of date citation (the S-3
gate in post_process asserts the citation is present — non-suppressible). Output language is
ja / en / bilingual. The report is ADVISORY (manager remediation), never an automated sanction.
"""

from __future__ import annotations

from typing import Any

_STATUS_LABEL = {
    "COMPLIANT": {"ja": "適合 (COMPLIANT)", "en": "COMPLIANT"},
    "NON_COMPLIANT": {"ja": "不適合 (NON_COMPLIANT)", "en": "NON_COMPLIANT"},
    "CONDITIONAL": {"ja": "条件付き適合 (CONDITIONAL)", "en": "CONDITIONAL"},
    # A pass that rests on a minority of the rule set is not the same statement as a
    # pass across all of it, and must not be printed as though it were.
    "COMPLIANT_LIMITED": {
        "ja": "限定的適合 (COMPLIANT — LIMITED SCOPE)",
        "en": "COMPLIANT — LIMITED SCOPE",
    },
    "UNKNOWN": {"ja": "判定不能 (UNKNOWN)", "en": "UNKNOWN"},
}


def render_report(
    compliance_status: str,
    check_results: list[dict[str, Any]],
    flagged_quotes: list[dict[str, Any]],
    remediation: list[str],
    applied_rules: list[dict[str, Any]],
    kb_version: str,
    kb_as_of_date: str,
    staff_id: str = "",
    interaction_context: str = "",
    output_language: str = "ja",
    coverage: dict[str, Any] | None = None,
) -> str:
    """Render the compliance status + per-rule results + flagged quotes + remediation + citation."""
    lang = output_language if output_language in ("ja", "en", "bilingual") else "ja"
    cov = coverage or {}
    limited = bool(cov.get("partial")) and compliance_status == "COMPLIANT"
    label = _STATUS_LABEL.get("COMPLIANT_LIMITED" if limited else compliance_status, _STATUS_LABEL["UNKNOWN"])
    lines: list[str] = []

    def add_both(ja: str, en: str) -> None:
        if lang in ("ja", "bilingual"):
            lines.append(ja)
        if lang in ("en", "bilingual"):
            lines.append(en)

    add_both(
        f"## 接客コンプラ監査結果: {label['ja']}",
        f"## Interaction Compliance Audit: {label['en']}",
    )
    if staff_id or interaction_context:
        add_both(
            f"対象: staff `{staff_id or '-'}` / 状況: {interaction_context or '-'}",
            f"Subject: staff `{staff_id or '-'}` / context: {interaction_context or '-'}",
        )
    lines.append("")

    if cov:
        add_both("### 監査範囲", "### Audit Scope")
        ev = ", ".join(cov.get("evaluated") or []) or "-"
        add_both(
            f"- 判定したルール ({cov.get('evaluated_count', 0)}/{cov.get('checked_count', 0)}): {ev}",
            f"- Rules that produced a judgement ({cov.get('evaluated_count', 0)}/"
            f"{cov.get('checked_count', 0)}): {ev}",
        )
        for s in cov.get("skipped") or []:
            add_both(
                f"- 未判定 [{s['check']}]: {s['reason']}",
                f"- NOT evaluated [{s['check']}]: {s['reason']}",
            )
        if limited:
            add_both(
                "- ⚠ 上記のうち判定できたルールの範囲内でのみ「適合」です。未判定のルール、"
                "および本ルールセットに定義のない行為(接客態度・不当な販売勧奨など)は"
                "**評価対象外**であり、問題がないことを意味しません。",
                "- ! This is a pass ONLY within the rules that produced a judgement. Rules "
                "not evaluated, and any conduct for which this rule set defines no rule "
                "(such as customer dignity or mis-selling), are **outside the scope of this "
                "audit** and their absence here does not mean nothing was wrong.",
            )
        lines.append("")

    add_both("### ルール別チェック結果", "### Per-Rule Check Results")
    for c in check_results:
        if c["result"] == "SKIP":
            continue
        lines.append(f"- [{c['check']}] {c['result']}: {c['detail']}")
    lines.append("")

    if flagged_quotes:
        add_both("### 指摘された非適合発言 (重大度)", "### Flagged Non-Compliant Quotes (severity)")
        for q in flagged_quotes:
            lines.append(f'- [{q["rule"]} / {q["severity"]}] "{q["quote"]}"')
        lines.append("")

    if remediation:
        add_both("### 店長向け是正アクション", "### Manager Remediation Actions")
        for r in remediation:
            lines.append(f"- {r}")
        lines.append("")

    add_both("### 適用ルール", "### Applied Rules")
    for rule in applied_rules:
        lines.append(f"- {rule.get('rule_id', '?')}: {rule.get('title', '')}")
    lines.append("")

    # MANDATORY citation (S-3 asserts kb_version + as-of date are present in the output).
    add_both(
        f"> 出典: 接客コンプラ KB `{kb_version}` (as of {kb_as_of_date}) / 消費者庁・景品表示法・"
        f"CAAアレルゲンガイダンス。本監査は情報提供・助言であり、自動的な処分ではありません。",
        f"> Source: retail interaction compliance KB `{kb_version}` (as of {kb_as_of_date}) / "
        f"消費者庁 · 景品表示法 · CAA allergen guidance. This audit is advisory, not an "
        f"automated sanction.",
    )
    return "\n".join(lines)
