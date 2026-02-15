"""
Salesforce Case Client - Case-specific business logic.

Auth comes from shared Lambda Layer: rackspace_sf_auth
This file contains ONLY case processing logic (updates, formatting, dedup).
"""

import contextlib
import json
import re
import logging
from datetime import datetime
from typing import Any, Optional

from rackspace_sf_auth import SalesforceAuthClient
from simple_salesforce import Salesforce

logger = logging.getLogger(__name__)


class SalesforceClient:
    """
    Salesforce case operations client.
    Delegates auth to shared rackspace_sf_auth layer.
    """

    def __init__(self) -> None:
        self._auth = SalesforceAuthClient()
        self._sf: Optional[Salesforce] = None

    def is_configured(self) -> bool:
        return self._auth.is_configured()

    def check_connection(self) -> dict[str, Any]:
        return self._auth.check_connection()

    def _get_connection(self) -> Optional[Salesforce]:
        if not self._sf:
            self._sf = self._auth.get_connection()
        return self._sf

    def query(self, soql: str) -> dict[str, Any]:
        """Run a SOQL query."""
        sf = self._get_connection()
        if sf is None:
            return {"records": [], "totalSize": 0}
        return sf.query(soql)

    def is_already_analyzed(self, case_id: str) -> bool:
        """Check if case was already analyzed today to prevent duplicate processing."""
        sf = self._get_connection()
        if sf is None or not case_id:
            return False
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            result = sf.query(
                f"SELECT AI_Analysis_Status__c, AI_Analyzed_Date__c "
                f"FROM Case WHERE Id = '{case_id}'"
            )
            if result["records"]:
                record = result["records"][0]
                status = record.get("AI_Analysis_Status__c")
                analyzed_date = record.get("AI_Analyzed_Date__c", "")
                if status == "Completed" and analyzed_date and analyzed_date.startswith(today):
                    return True
            return False
        except Exception:
            return False

    def update_case_analysis(self, case_id: str, analysis: dict[str, Any]) -> bool:
        """Update Salesforce Case with AI analysis results."""
        sf = self._get_connection()
        if sf is None:
            logger.warning(f"Skipping SF update for {case_id} - not connected")
            return False
        try:
            update_data = {
                "AI_Analysis__c": self._format_analysis(analysis),
                "AI_Suggestions__c": self._format_steps(analysis.get("steps", [])),
                "Self_Resolvable__c": analysis.get("self_resolvable", False),
                "Similar_Cases__c": self._format_similar_cases(analysis.get("similar_cases", [])),
                "AI_Analyzed_Date__c": datetime.utcnow().isoformat(),
                "AI_Analysis_Status__c": "Completed",
            }
            sf.Case.update(case_id, update_data)
            logger.info(f"Updated Case {case_id} with analysis")
            return True
        except Exception as e:
            logger.error(f"Failed to update Case {case_id}: {e}")
            with contextlib.suppress(Exception):
                sf.Case.update(case_id, {
                    "AI_Analysis_Status__c": "Failed",
                    "AI_Analysis__c": f"Analysis failed: {e!s}",
                })
            return False

    def _format_analysis(self, analysis: dict[str, Any]) -> str:
        """Format analysis as HTML for Rich Text field."""
        parts: list[str] = []
        sections = [
            ("summary", "Summary"),
            ("root_cause", "Root Cause"),
            ("recommendation", "Recommendation"),
            ("estimated_resolution", "Estimated Resolution"),
            ("category", "Category"),
            ("severity", "Severity"),
        ]
        for key, label in sections:
            if analysis.get(key):
                parts.append(f"<b>{label}</b><br/>{analysis[key]}")
        # If agent returned very little, dump all string fields as fallback
        if len(parts) <= 1:
            for k, v in analysis.items():
                if isinstance(v, str) and v and k not in ("analyzed_date", "ai_disclaimer") and not any(k == s[0] for s in sections):
                    parts.append(f"<b>{k.replace('_', ' ').title()}</b><br/>{v}")
        if analysis.get("escalation_needed") and analysis.get("escalation_reason"):
            parts.append(f"<b>Escalation Required</b><br/>{analysis['escalation_reason']}")
        if analysis.get("kb_articles"):
            articles = analysis["kb_articles"]
            if isinstance(articles, list) and articles:
                sf = self._get_connection()
                base = f"https://{sf.sf_instance}" if sf else ""
                real_ka = set(analysis.get("_real_ka_titles", []))
                items = []
                for a in articles:
                    if base and isinstance(a, str) and a.lower() in real_ka:
                        url_name = a.replace(" ", "-")
                        items.append(f'<li><a href="{base}/articles/Knowledge/{url_name}" target="_blank">{a}</a></li>')
                    else:
                        items.append(f"<li>{a}</li>")
                parts.append(f"<b>KB Sources</b><ul>{''.join(items)}</ul>")
        parts.append("<i>[AI-Generated Analysis - Please verify before taking action]</i>")
        return "<br/><br/>".join(parts) if parts else json.dumps(analysis, indent=2)

    def _format_steps(self, steps: list[str]) -> str:
        """Format steps as HTML with section headers for Rich Text field."""
        if not steps:
            return ""
        html_parts = []
        current_items = []
        for step in steps:
            s = step.strip()
            # Section headers (ADMIN STEPS:, USER SELF-SERVICE STEPS:)
            if s.endswith("STEPS:") or s.endswith("STEPS"):
                if current_items:
                    html_parts.append("<ol>" + "".join(f"<li>{i}</li>" for i in current_items) + "</ol>")
                    current_items = []
                html_parts.append(f"<br/><b>{s}</b>")
            else:
                current_items.append(re.sub(r'^\d+\.\s*', '', s))
        if current_items:
            html_parts.append("<ol>" + "".join(f"<li>{i}</li>" for i in current_items) + "</ol>")
        html_parts.append("<i>[AI-Generated Suggestions - Please verify before taking action]</i>")
        return "".join(html_parts)

    def _format_similar_cases(self, cases: list[str]) -> str:
        """Format similar cases as HTML hyperlinks with subject for Rich Text field."""
        if not cases:
            return ""

        sf = self._get_connection()
        if not sf:
            return "<br/>".join(f"• Case {c}" for c in cases[:5])

        instance_url = getattr(sf, 'sf_instance', '') or ''
        if instance_url and not instance_url.startswith('http'):
            instance_url = f"https://{instance_url}"

        # Extract case numbers (handle both "00141762" and "#00141762: description" formats)
        case_numbers = []
        for case in cases[:5]:
            num_match = re.search(r'#?(\d{8})', str(case))
            if num_match:
                case_numbers.append(num_match.group(1))

        if not case_numbers:
            return "<br/>".join(f"• {c}" for c in cases[:5])

        # Bulk lookup: get Id + Subject for all case numbers
        numbers_str = "','".join(case_numbers)
        try:
            result = sf.query(
                f"SELECT Id, CaseNumber, Subject FROM Case WHERE CaseNumber IN ('{numbers_str}')"
            )
            case_map = {
                r["CaseNumber"]: {"id": r["Id"], "subject": r.get("Subject", "")}
                for r in result.get("records", [])
            }
        except Exception:
            case_map = {}

        formatted = []
        for num in case_numbers:
            info = case_map.get(num)
            if info and instance_url:
                subject = info["subject"][:80] if info["subject"] else "No Subject"
                link = f'<a href="{instance_url}/{info["id"]}" target="_blank">Case {num}</a>: {subject}'
                formatted.append(f"• {link}")
            else:
                formatted.append(f"• Case {num}")

        header = f"<b>Top {len(formatted)} most recent similar closed cases:</b><br/>"
        footer = "<br/><i>[AI-Generated - Similar cases retrieved from Salesforce. Please verify relevance.]</i>"
        return header + "<br/>".join(formatted) + footer
