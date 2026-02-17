"""
Tests for case_processor/salesforce_client.py — SF update and HTML formatting.
Run: python3 -m pytest tests/test_salesforce_client.py -v
"""

import json
import re
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


# =============================================================================
# FORMAT ANALYSIS
# =============================================================================

class TestFormatAnalysis:
    def _client(self, sf_client_module, mock_sf):
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf
        return c

    def test_all_sections(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_analysis({
            "summary": "Test", "root_cause": "Cause", "recommendation": "Do this",
            "estimated_resolution": "15 min", "category": "Opportunity", "severity": "Medium",
        })
        for label in ["Summary", "Root Cause", "Recommendation", "Category", "Severity"]:
            assert f"<b>{label}</b>" in html

    def test_kb_hyperlink_with_url_map(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_analysis({
            "summary": "Test",
            "kb_articles": ["Sales Managers \u2013 How to modify amount?"],
            "_real_ka_titles": ["sales managers \u2013 how to modify amount?"],
            "_ka_url_map": {"sales managers \u2013 how to modify amount?": "Sales-Managers-How-to-modify-amount"},
        })
        assert "Sales-Managers-How-to-modify-amount" in html
        assert 'target="_blank"' in html

    def test_sop_no_hyperlink(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_analysis({
            "summary": "Test", "kb_articles": ["Amount SOP"], "_real_ka_titles": [], "_ka_url_map": {},
        })
        assert "<a href" not in html

    def test_missing_urlname_plain_text(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_analysis({
            "summary": "Test", "kb_articles": ["Article"], "_real_ka_titles": ["article"], "_ka_url_map": {},
        })
        assert "<a href" not in html
        assert "<li>Article</li>" in html

    def test_escalation(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_analysis({
            "summary": "Test", "escalation_needed": True, "escalation_reason": "Manager approval",
        })
        assert "Escalation Required" in html


# =============================================================================
# FORMAT STEPS
# =============================================================================

class TestFormatSteps:
    def _client(self, sf_client_module, mock_sf):
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf
        return c

    def test_sections_and_ol(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_steps(
            ["ADMIN STEPS:", "1. Do admin", "USER SELF-SERVICE STEPS:", "1. Do user"],
            self_resolvable=True,
        )
        assert "<b>ADMIN STEPS:</b>" in html
        assert "<b>USER SELF-SERVICE STEPS:</b>" in html
        assert "User can also self-resolve this." in html
        assert "<ol>" in html

    def test_strips_numbers(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_steps(["ADMIN STEPS:", "1. First"])
        assert "<li>First</li>" in html

    def test_user_only_steps_get_admin_path(self, sf_client_module, mock_sf_connection):
        html = self._client(sf_client_module, mock_sf_connection)._format_steps(
            ["USER SELF-SERVICE STEPS:", "1. Do user action"],
            self_resolvable=True,
        )
        assert "<b>ADMIN STEPS:</b>" in html
        assert "Review the request context and validate required fields/metadata." in html
        assert "No admin action is needed" not in html
        assert "<b>USER SELF-SERVICE STEPS:</b>" in html

    def test_empty(self, sf_client_module, mock_sf_connection):
        assert self._client(sf_client_module, mock_sf_connection)._format_steps([]) == ""


# =============================================================================
# FORMAT SIMILAR CASES
# =============================================================================

class TestFormatSimilarCases:
    def _client(self, sf_client_module, mock_sf):
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf
        return c

    def test_hyperlinks(self, sf_client_module, mock_sf_connection):
        mock_sf_connection.query.return_value = {"records": [
            {"Id": "500X", "CaseNumber": "00131235", "Subject": "Update amount"},
        ]}
        html = self._client(sf_client_module, mock_sf_connection)._format_similar_cases(["00131235"])
        assert 'href="https://rax--inttest.sandbox.my.salesforce.com/500X"' in html

    def test_empty(self, sf_client_module, mock_sf_connection):
        assert self._client(sf_client_module, mock_sf_connection)._format_similar_cases([]) == ""

    def test_query_failure_graceful(self, sf_client_module, mock_sf_connection):
        mock_sf_connection.query.side_effect = Exception("SOQL error")
        html = self._client(sf_client_module, mock_sf_connection)._format_similar_cases(["00131235"])
        assert "00131235" in html


# =============================================================================
# UPDATE CASE
# =============================================================================

class TestUpdateCase:
    def test_success(self, sf_client_module, mock_sf_connection):
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf_connection
        assert c.update_case_analysis("500X", {"summary": "Test"}) is True

    def test_failure_sets_error(self, sf_client_module, mock_sf_connection):
        mock_sf_connection.Case.update.side_effect = [Exception("API error"), None]
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf_connection
        assert c.update_case_analysis("500X", {"summary": "Test"}) is False
        assert mock_sf_connection.Case.update.call_count == 2


# =============================================================================
# IS ALREADY ANALYZED
# =============================================================================

class TestIsAlreadyAnalyzed:
    def test_today(self, sf_client_module, mock_sf_connection):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mock_sf_connection.query.return_value = {"records": [
            {"AI_Analysis_Status__c": "Completed", "AI_Analyzed_Date__c": f"{today}T10:00:00Z"}
        ]}
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf_connection
        assert c.is_already_analyzed("500X") is True

    def test_not_analyzed(self, sf_client_module, mock_sf_connection):
        mock_sf_connection.query.return_value = {"records": [
            {"AI_Analysis_Status__c": None, "AI_Analyzed_Date__c": None}
        ]}
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf_connection
        assert c.is_already_analyzed("500X") is False

    def test_empty_id(self, sf_client_module, mock_sf_connection):
        c = sf_client_module.SalesforceClient()
        c._sf = mock_sf_connection
        assert c.is_already_analyzed("") is False
