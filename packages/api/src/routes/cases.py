"""Case CRUD endpoints with in-memory store for MVP."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from src.routes._store import case_store
from src.services.model_gateway import resolve_model

router = APIRouter(tags=["cases"])


@router.get("/cases")
async def list_cases():
    """List all cases for the authenticated attorney."""
    return [
        {
            "id": case_id,
            "stage": orch.case_state.stage.value if orch.case_state else "UNKNOWN",
            "jurisdiction": orch.case_state.jurisdiction if orch.case_state else "",
            "created_at": (orch.case_state.created_at.isoformat() if orch.case_state else ""),
        }
        for case_id, orch in case_store.items()
    ]


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get full case state by ID."""
    orch = case_store.get(case_id)
    if not orch:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return orch.get_case_state_snapshot()


@router.get("/cases/{case_id}/status")
async def get_case_status(case_id: str):
    """Get pipeline status for a case — what stage it's at, what's blocked."""
    orch = case_store.get(case_id)
    if not orch:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return {**orch.get_status().to_dict(), "model": resolve_model(orch.run_model)}


@router.get("/cases/{case_id}/merge-history")
async def get_merge_history(case_id: str):
    """Get the Orchestrator's merge decision history for a case."""
    orch = case_store.get(case_id)
    if not orch:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return orch.get_merge_history()


@router.get("/cases/{case_id}/summary", response_class=HTMLResponse)
async def get_case_summary(case_id: str):
    """Human-readable HTML summary of everything the pipeline found."""
    orch = case_store.get(case_id)
    if not orch:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = orch.get_case_state_snapshot()
    status = orch.get_status()
    history = orch.get_merge_history()

    # --- Extract data ---
    cp = state.get("charge_processing", {}) or {}
    cp_data = cp.get("data", {})

    pi = state.get("pre_interview_research", {}) or {}
    pi_data = pi.get("data", {})

    defendant = cp_data.get("defendant", {})
    charges = cp_data.get("charges", [])
    persons = cp_data.get("persons_of_interest", [])
    misconduct = cp_data.get("misconduct_flags", [])
    allegations = cp_data.get("factual_allegations", [])
    evidence = cp_data.get("evidence_items", [])
    meta = cp_data.get("processing_metadata", {})

    tqs = pi_data.get("targeted_questions", [])
    rfs = pi_data.get("preliminary_rights_flags", [])
    known_facts = pi_data.get("known_facts_from_documents", [])
    collateral = pi_data.get("collateral_consequence_alerts", [])
    legal_brief = pi_data.get("legal_brief", {})

    # --- Build HTML ---
    def _esc(val):
        """Escape HTML characters."""
        return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _badge(level):
        colors = {
            "HIGH": "#22c55e",
            "MEDIUM": "#f59e0b",
            "LOW": "#ef4444",
            "high": "#ef4444",
            "medium": "#f59e0b",
            "low": "#22c55e",
            "MUST_ASK": "#ef4444",
            "SHOULD_ASK": "#f59e0b",
            "IF_TIME": "#6b7280",
        }
        color = colors.get(str(level), "#6b7280")
        return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.8em;font-weight:600">{_esc(level)}</span>'

    html_parts = [
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Case {_esc(case_id)} — DEFENDER AI</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ border-bottom: 3px solid #1e40af; padding-bottom: 8px; }}
  h2 {{ color: #1e40af; margin-top: 32px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
  h3 {{ color: #374151; }}
  .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 12px 0; }}
  .card-red {{ background: #fef2f2; border-color: #fecaca; }}
  .card-green {{ background: #f0fdf4; border-color: #bbf7d0; }}
  .card-yellow {{ background: #fffbeb; border-color: #fde68a; }}
  .card-blue {{ background: #eff6ff; border-color: #bfdbfe; }}
  table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }}
  th {{ background: #f1f5f9; font-weight: 600; }}
  .meta {{ color: #6b7280; font-size: 0.9em; }}
  .pipeline-step {{ display: inline-block; padding: 4px 12px; margin: 2px; border-radius: 20px; font-size: 0.85em; }}
  .step-done {{ background: #dcfce7; color: #166534; }}
  .step-current {{ background: #dbeafe; color: #1e40af; font-weight: 600; }}
  .step-pending {{ background: #f1f5f9; color: #9ca3af; }}
</style></head><body>
<h1>Case {_esc(case_id)}</h1>
"""
    ]

    # Low confidence warning
    low_conf = cp_data.get("_low_confidence_flag") or pi_data.get("_low_confidence_flag")
    if low_conf:
        html_parts.append(
            """
<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:8px;padding:16px;margin:16px 0">
<strong style="color:#dc2626">&#9888; LOW CONFIDENCE — ATTORNEY REVIEW REQUIRED</strong><br>
One or more pipeline stages returned low confidence results.
The data below has been flagged and should be independently verified before relying on it.
</div>"""
        )

    # Pipeline status bar
    all_stages = [
        "CREATED",
        "CHARGES_PROCESSING",
        "CHARGES_PROCESSED",
        "PRE_INTERVIEW_RESEARCH",
        "PRE_INTERVIEW_COMPLETE",
        "INTAKE_IN_PROGRESS",
        "INTAKE_COMPLETE",
    ]
    current = (
        status.current_stage.value
        if hasattr(status.current_stage, "value")
        else str(status.current_stage)
    )
    completed = set(status.completed_stages)
    html_parts.append('<div style="margin:16px 0">')
    for s in all_stages:
        if s in completed:
            cls = "step-done"
        elif s == current:
            cls = "step-current"
        else:
            cls = "step-pending"
        label = s.replace("_", " ").title()
        html_parts.append(f'<span class="pipeline-step {cls}">{label}</span>')
    html_parts.append("</div>")

    # Merge history
    if history:
        html_parts.append('<div class="meta">Pipeline decisions: ')
        for h in history:
            html_parts.append(
                f'{h["agent_id"]} → {_badge(h.get("confidence", "?"))} {h["decision"]} &nbsp; '
            )
        html_parts.append("</div>")

    # Defendant
    if defendant:
        html_parts.append(
            f"""
<h2>Defendant</h2>
<div class="card">
<strong>{_esc(defendant.get('name', 'UNKNOWN'))}</strong><br>
DOB: {_esc(defendant.get('date_of_birth', 'Unknown'))}<br>
Address: {_esc(defendant.get('address', 'Unknown'))}<br>
Custody: {_esc(defendant.get('custody_status', 'Unknown'))}<br>
Prior record: {'Yes — ' + _esc(defendant.get('prior_record_details', '')) if defendant.get('prior_record_mentioned') else 'None mentioned'}
</div>"""
        )

    # Charges
    if charges:
        html_parts.append(f"<h2>Charges ({len(charges)})</h2>")
        for c in charges:
            statute = c.get("statute", {})
            penalty = c.get("penalty_range", {})
            html_parts.append(
                f"""
<div class="card">
<strong>Count {_esc(c.get('count_number', '?'))}: {_esc(c.get('charge_description', ''))}</strong>
{_badge(str(round(c.get('confidence', 0), 2)) + ' confidence')}<br>
Statute: <code>{_esc(statute.get('code', ''))}</code><br>
Degree: {_esc(c.get('degree', ''))}<br>
Classification: {_esc(c.get('classification', ''))}<br>"""
            )
            if penalty:
                html_parts.append(
                    f"Penalty: {_esc(penalty.get('minimum', '?'))} — {_esc(penalty.get('maximum', '?'))}"
                )
                if penalty.get("mandatory_minimum"):
                    html_parts.append(f" (mandatory minimum: {_esc(penalty['mandatory_minimum'])})")
                html_parts.append("<br>")
            elements = c.get("elements", [])
            if elements:
                html_parts.append("<br><strong>Elements prosecution must prove:</strong><ol>")
                for el in elements:
                    if isinstance(el, dict):
                        html_parts.append(f"<li>{_esc(el.get('element', ''))}")
                        support = el.get("factual_support_in_charging_document")
                        if support:
                            html_parts.append(
                                f" <span class='meta'>— Document support: {_esc(support)}</span>"
                            )
                        html_parts.append("</li>")
                    else:
                        html_parts.append(f"<li>{_esc(el)}</li>")
                html_parts.append("</ol>")
            enhancements = c.get("enhancements", [])
            if enhancements:
                html_parts.append("<strong>Enhancements:</strong><ul>")
                for e in enhancements:
                    html_parts.append(
                        f"<li>{_esc(e.get('type', ''))}: {_esc(e.get('additional_penalty', ''))}</li>"
                    )
                html_parts.append("</ul>")
            html_parts.append("</div>")

    # Misconduct Flags
    if misconduct:
        html_parts.append(f"<h2>Misconduct Flags ({len(misconduct)})</h2>")
        for m in misconduct:
            card_cls = "card-red" if m.get("severity") == "high" else "card-yellow"
            html_parts.append(
                f"""
<div class="card {card_cls}">
{_badge(m.get('severity', '?'))} <strong>{_esc(m.get('category', ''))}</strong>
— {_esc(m.get('subcategory', ''))}<br>
{_esc(m.get('description', ''))}<br>
<span class="meta">Factual basis: {_esc(m.get('factual_basis', ''))}</span><br>
<span class="meta">Legal significance: {_esc(m.get('legal_significance', ''))}</span>
</div>"""
            )

    # Rights Flags from Pre-Interview
    if rfs:
        html_parts.append(f"<h2>Preliminary Rights Flags ({len(rfs)})</h2>")
        for rf in rfs:
            card_cls = "card-red" if rf.get("severity") == "high" else "card-yellow"
            html_parts.append(
                f"""
<div class="card {card_cls}">
{_badge(rf.get('severity', '?'))} <strong>{_esc(rf.get('type', ''))}</strong><br>
{_esc(rf.get('description', ''))}<br>
<span class="meta">Basis: {_esc(rf.get('basis', ''))}</span><br>
<span class="meta">Investigate: {_esc(rf.get('investigation_needed', ''))}</span>
</div>"""
            )

    # Targeted Questions
    if tqs:
        html_parts.append(f"<h2>Targeted Intake Questions ({len(tqs)})</h2>")
        html_parts.append("<table><tr><th>Priority</th><th>Question</th><th>Targets</th></tr>")
        for q in tqs:
            html_parts.append(
                f"""<tr>
<td>{_badge(q.get('priority', '?'))}</td>
<td>{_esc(q.get('question', ''))}</td>
<td class="meta">{_esc(q.get('relevant_element', ''))}</td>
</tr>"""
            )
        html_parts.append("</table>")

    # Persons of Interest
    if persons:
        html_parts.append(f"<h2>Persons of Interest ({len(persons)})</h2>")
        html_parts.append(
            "<table><tr><th>Name</th><th>Role</th><th>Badge/Agency</th><th>Details</th></tr>"
        )
        for p in persons:
            html_parts.append(
                f"""<tr>
<td><strong>{_esc(p.get('name', '?'))}</strong></td>
<td>{_esc(p.get('role', '?'))}</td>
<td>{_esc(p.get('badge_number', '') or '')} {_esc(p.get('agency', '') or '')}</td>
<td class="meta">{_esc(p.get('involvement_summary', '') or p.get('potential_impeachment_notes', ''))}</td>
</tr>"""
            )
        html_parts.append("</table>")

    # Factual Allegations
    if allegations:
        html_parts.append(f"<h2>Factual Allegations ({len(allegations)})</h2>")
        for a in allegations:
            html_parts.append(
                f"""
<div class="card">
<strong>{_esc(a.get('allegation_id', a.get('id', '?')))}</strong>: {_esc(a.get('summary', a.get('allegation', '')))}
{_badge(str(round(a.get('confidence', 0), 2)))}<br>
<span class="meta">{_esc(a.get('detail', ''))}</span>
{'<br><strong style=color:#166534>Exculpatory potential:</strong> ' + _esc(a.get('exculpatory_notes', '')) if a.get('exculpatory_potential') else ''}
</div>"""
            )

    # Collateral Consequence Alerts
    if collateral:
        html_parts.append(f"<h2>Collateral Consequence Alerts ({len(collateral)})</h2>")
        for cc in collateral:
            html_parts.append(
                f"""
<div class="card card-blue">
{_badge(cc.get('severity', '?'))} <strong>{_esc(cc.get('category', ''))}</strong><br>
{_esc(cc.get('description', ''))}<br>
<span class="meta">Ask at intake: {_esc(cc.get('intake_question', ''))}</span>
</div>"""
            )

    # Known Facts
    if known_facts:
        html_parts.append(f"<h2>Known Facts from Documents ({len(known_facts)})</h2>")
        html_parts.append("<table><tr><th>Fact</th><th>Category</th><th>Verify?</th></tr>")
        for kf in known_facts:
            html_parts.append(
                f"""<tr>
<td>{_esc(kf.get('fact', ''))}</td>
<td>{_esc(kf.get('category', ''))}</td>
<td>{'Yes' if kf.get('verify_with_client') else 'No'}</td>
</tr>"""
            )
        html_parts.append("</table>")

    # Legal Brief
    if legal_brief:
        html_parts.append("<h2>Legal Brief</h2>")
        issues = legal_brief.get("key_legal_issues", [])
        if issues:
            html_parts.append("<h3>Key Legal Issues</h3><ul>")
            for i in issues:
                html_parts.append(f"<li>{_esc(i)}</li>")
            html_parts.append("</ul>")
        defenses = legal_brief.get("potential_defenses", [])
        if defenses:
            html_parts.append("<h3>Potential Defenses</h3><ul>")
            for d in defenses:
                html_parts.append(f"<li>{_esc(d)}</li>")
            html_parts.append("</ul>")
        div_elig = legal_brief.get("diversion_eligibility", {})
        if div_elig:
            html_parts.append("<h3>Diversion Eligibility</h3><div class='card card-green'>")
            for k, v in div_elig.items():
                html_parts.append(
                    f"<strong>{_esc(k.replace('_', ' ').title())}:</strong> {_esc(v)}<br>"
                )
            html_parts.append("</div>")

    # Evidence
    if evidence:
        html_parts.append(f"<h2>Evidence Items ({len(evidence)})</h2>")
        html_parts.append(
            "<table><tr><th>Description</th><th>Type</th><th>Chain of Custody</th></tr>"
        )
        for e in evidence:
            html_parts.append(
                f"""<tr>
<td>{_esc(e.get('description', ''))}</td>
<td>{_esc(e.get('type', ''))}</td>
<td class="meta">{_esc(e.get('chain_of_custody_notes', '') or 'N/A')}</td>
</tr>"""
            )
        html_parts.append("</table>")

    # Confidence summary
    conf_summary = meta.get("confidence_summary", {})
    if conf_summary:
        total = sum(conf_summary.values())
        html_parts.append(
            f"""
<h2>Confidence Summary</h2>
<div class="card">
<strong>{total} items extracted</strong> — {meta.get('review_required_count', 0)} needing attorney review<br><br>
<div style="display:flex;height:24px;border-radius:4px;overflow:hidden;margin:8px 0">"""
        )
        colors = {
            "very_high": "#22c55e",
            "high": "#4ade80",
            "medium": "#fbbf24",
            "low": "#f97316",
            "very_low": "#ef4444",
        }
        for bucket, color in colors.items():
            count = conf_summary.get(bucket, 0)
            pct = (count / total * 100) if total > 0 else 0
            if pct > 0:
                html_parts.append(
                    f'<div style="background:{color};width:{pct}%" title="{bucket}: {count}"></div>'
                )
        html_parts.append(
            f"""</div>
<span class="meta">Very High: {conf_summary.get('very_high', 0)} | High: {conf_summary.get('high', 0)} | Medium: {conf_summary.get('medium', 0)} | Low: {conf_summary.get('low', 0)} | Very Low: {conf_summary.get('very_low', 0)}</span>
</div>"""
        )

    # Ethical flags
    ethical_flags = state.get("ethical_flags", [])
    if ethical_flags:
        html_parts.append(f"<h2>Ethical Flags ({len(ethical_flags)})</h2>")
        for ef in ethical_flags:
            html_parts.append(
                f"""
<div class="card card-red">
{_badge(ef.get('priority', '?'))} <strong>{_esc(ef.get('category', ''))}</strong><br>
{_esc(ef.get('description', ''))}<br>
<span class="meta">Source: {_esc(ef.get('agent_source', ''))}</span>
</div>"""
            )

    html_parts.append(
        """
<hr style="margin-top:40px">
<p class="meta">Generated by DEFENDER AI — Attorney review required before any action is taken.
All outputs are attorney work product and protected by attorney-client privilege.</p>
</body></html>"""
    )

    return "\n".join(html_parts)
