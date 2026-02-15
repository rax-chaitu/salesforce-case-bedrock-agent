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
        """Format analysis dict as plain text for Long Text Area field."""
        parts: list[str] = []
        if analysis.get("summary"):
            parts.append(f"SUMMARY\n{analysis['summary']}")
        if analysis.get("root_cause"):
            parts.append(f"ROOT CAUSE\n{analysis['root_cause']}")
        if analysis.get("recommendation"):
            parts.append(f"RECOMMENDATION\n{analysis['recommendation']}")
        if analysis.get("estimated_resolution"):
            parts.append(f"ESTIMATED RESOLUTION\n{analysis['estimated_resolution']}")
        if analysis.get("escalation_needed") and analysis.get("escalation_reason"):
            parts.append(f"ESCALATION REQUIRED\n{analysis['escalation_reason']}")
        if analysis.get("category"):
            parts.append(f"CATEGORY\n{analysis['category']}")
        if analysis.get("kb_articles"):
            articles = analysis["kb_articles"]
            if isinstance(articles, list) and articles:
                articles_text = "\n".join(f"• {a}" for a in articles)
                parts.append(f"KB SOURCES\n{articles_text}")
        parts.append("[AI-Generated Analysis - Please verify before taking action]")
        return "\n\n".join(parts) if parts else json.dumps(analysis, indent=2)

    def _format_steps(self, steps: list[str]) -> str:
        """Format steps list as plain numbered text."""
        if not steps:
            return ""
        clean_steps = [re.sub(r'^\d+\.\s*', '', step.strip()) for step in steps]
        formatted = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(clean_steps))
        formatted += "\n\n[AI-Generated Suggestions - Please verify before taking action]"
        return formatted

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
