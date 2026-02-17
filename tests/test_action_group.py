"""
Tests for action_group/handler.py — Bedrock Agent action group.
Run: python3 -m pytest tests/test_action_group.py -v
"""

import json
import re
import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# QUERY BUILDING (pure logic)
# =============================================================================

class TestQueryBuilding:
    def _build(self, keywords="", support_reason="", tool=""):
        conditions = ["Status IN ('Closed', 'Closed Resolved')", "ClosedDate != null"]
        keyword_conditions = []
        for word in [w for w in keywords.split()[:5] if len(w) > 2]:
            keyword_conditions.append(f"Subject LIKE '%{word.replace(chr(39), chr(92)+chr(39))}%'")
        if support_reason:
            conditions.append(f"Support_Reason__c = '{support_reason.replace(chr(39), chr(92)+chr(39))}'")
            if keyword_conditions:
                conditions.append(f"({' OR '.join(keyword_conditions)})")
        elif keyword_conditions:
            conditions.append(f"({' OR '.join(keyword_conditions)})")
        if tool:
            conditions.append(f"Tool__c = '{tool.replace(chr(39), chr(92)+chr(39))}'")
        return " AND ".join(conditions)

    def test_includes_closed_resolved(self):
        assert "Closed Resolved" in self._build(keywords="test")

    def test_no_duplicate_status(self):
        assert self._build(keywords="test", support_reason="Opp", tool="SF").count("Status") == 1

    def test_closeddate(self):
        assert "ClosedDate != null" in self._build()

    def test_reason_and_keywords(self):
        w = self._build(keywords="Add Partner", support_reason="Opp - Amount")
        assert "Support_Reason__c" in w and "Subject LIKE" in w

    def test_tool(self):
        assert "Tool__c = 'Salesforce'" in self._build(tool="Salesforce")

    def test_short_words_skipped(self):
        w = self._build(keywords="Add me to opp")
        assert "'me'" not in w and "'to'" not in w

    def test_quotes_escaped(self):
        assert "\\'" in self._build(support_reason="O'Brien")


# =============================================================================
# CONTENT SCORING (pure logic)
# =============================================================================

class TestContentScoring:
    def _score(self, r):
        comments = len((r.get("CaseComments") or {}).get("records", []))
        emails = len((r.get("EmailMessages") or {}).get("records", []))
        return (comments * 3) + (emails * 2) + (1 if r.get("Case_Closure_Notes__c") else 0) + (1 if r.get("DP_Resolution__c") else 0)

    def test_rich_higher(self):
        rich = {"CaseComments": {"records": [{"CommentBody": "c"}]}, "EmailMessages": {"records": [{"TextBody": "e"}]},
                "Case_Closure_Notes__c": "Done", "DP_Resolution__c": "OK"}
        assert self._score(rich) > self._score({})

    def test_empty_zero(self):
        assert self._score({}) == 0

    def test_formula(self):
        assert self._score({"CaseComments": {"records": [{"CommentBody": "c1"}, {"CommentBody": "c2"}]},
                            "EmailMessages": {"records": [{"TextBody": "e1"}, {"TextBody": "e2"}, {"TextBody": "e3"}]},
                            "Case_Closure_Notes__c": "N", "DP_Resolution__c": "R"}) == 14

    def test_none_safe(self):
        assert self._score({"CaseComments": None, "EmailMessages": None}) == 0


# =============================================================================
# SEARCH SIMILAR CASES (mocked SF)
# =============================================================================

class TestSearchSimilarCases:
    def test_returns_cases(self, action_handler, sample_similar_cases_records):
        mock_sf = MagicMock()
        mock_sf.query.side_effect = [sample_similar_cases_records, {"records": []}]
        with patch.object(action_handler, "get_sf", return_value=mock_sf):
            result = action_handler.search_similar_cases({"keywords": "Update amount", "support_reason": "Opp", "case_tool": "SF", "max_results": "10"})
        assert result["total_found"] == 2
        assert result["cases"][0]["case_number"] == "00131235"

    def test_content_rich_ranked_first(self, action_handler):
        records = {"records": [
            {"Id": "A", "CaseNumber": "00200001", "Subject": "T", "Support_Reason__c": "", "Description": "",
             "Case_Closure_Notes__c": None, "ClosedDate": "2025-06-01", "Close_Codes__c": None, "Close_Reason__c": None,
             "Root_Cause_of_Inquiry__c": None, "Tool__c": "", "Department__c": None, "Segment__c": None,
             "DP_Resolution__c": None, "Admin_Notes__c": None, "CaseComments": None, "EmailMessages": None},
            {"Id": "B", "CaseNumber": "00100001", "Subject": "T", "Support_Reason__c": "", "Description": "",
             "Case_Closure_Notes__c": "Done", "ClosedDate": "2024-01-01", "Close_Codes__c": None, "Close_Reason__c": None,
             "Root_Cause_of_Inquiry__c": None, "Tool__c": "", "Department__c": None, "Segment__c": None,
             "DP_Resolution__c": "OK", "Admin_Notes__c": None,
             "CaseComments": {"records": [{"CommentBody": "c1"}]}, "EmailMessages": {"records": [{"Subject": "Re:", "TextBody": "e"}]}},
        ], "totalSize": 2}
        mock_sf = MagicMock()
        mock_sf.query.side_effect = [records, {"records": []}]
        with patch.object(action_handler, "get_sf", return_value=mock_sf):
            result = action_handler.search_similar_cases({"keywords": "Test", "max_results": "10"})
        assert result["cases"][0]["case_number"] == "00100001"

    def test_keyword_fallback_to_reason_tool_when_zero_results(self, action_handler, sample_similar_cases_records):
        mock_sf = MagicMock()
        # 1) strict keyword query returns none, 2) fallback query returns records, 3) chatter query
        mock_sf.query.side_effect = [
            {"records": [], "totalSize": 0},
            sample_similar_cases_records,
            {"records": []},
        ]
        with patch.object(action_handler, "get_sf", return_value=mock_sf):
            result = action_handler.search_similar_cases(
                {
                    "keywords": "CODX E2E Inttest 20260217131758",
                    "support_reason": "Opportunity - Add/Change Team Member or Split",
                    "case_tool": "Salesforce",
                    "max_results": "10",
                }
            )

        assert result["total_found"] == 2
        assert mock_sf.query.call_count == 3
        first_query = mock_sf.query.call_args_list[0].args[0]
        second_query = mock_sf.query.call_args_list[1].args[0]
        assert "Subject LIKE" in first_query
        assert "Subject LIKE" not in second_query
        assert "Support_Reason__c = 'Opportunity - Add/Change Team Member or Split'" in second_query
        assert "Tool__c = 'Salesforce'" in second_query


# =============================================================================
# SEARCH KNOWLEDGE ARTICLES
# =============================================================================

class TestSearchKnowledgeArticles:
    def test_returns_matching(self, action_handler):
        mock_sf = MagicMock()
        mock_sf.query.return_value = {"records": [
            {"Title": "Opportunity Amount Guide", "UrlName": "Opp", "ArticleNumber": "KA1", "Summary": "How to"},
        ]}
        with patch.object(action_handler, "get_sf", return_value=mock_sf):
            result = action_handler.search_knowledge_articles({"keywords": "Opportunity Amount"})
        assert result["total_found"] >= 1


# =============================================================================
# LAMBDA HANDLER ROUTING
# =============================================================================

class TestActionGroupRouting:
    def _event(self, path, params):
        return {"apiPath": path, "httpMethod": "POST", "actionGroup": "ag",
                "requestBody": {"content": {"application/json": {"properties": [{"name": k, "value": v} for k, v in params.items()]}}}}

    def test_routes_similar_cases(self, action_handler):
        with patch.object(action_handler, "search_similar_cases", return_value={"cases": [], "total_found": 0}) as m:
            action_handler.lambda_handler(self._event("/searchSimilarCases", {"keywords": "t"}), None)
            m.assert_called_once()

    def test_routes_kav(self, action_handler):
        with patch.object(action_handler, "search_knowledge_articles", return_value={"articles": [], "total_found": 0}) as m:
            action_handler.lambda_handler(self._event("/searchKnowledgeArticles", {"keywords": "t"}), None)
            m.assert_called_once()

    def test_unknown_path(self, action_handler):
        result = action_handler.lambda_handler(self._event("/unknown", {}), None)
        body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
        assert "error" in body

    def test_error_returns_empty(self, action_handler):
        with patch.object(action_handler, "search_similar_cases", side_effect=Exception("DB error")):
            result = action_handler.lambda_handler(self._event("/searchSimilarCases", {"keywords": "t"}), None)
            body = json.loads(result["response"]["responseBody"]["application/json"]["body"])
            assert body["total_found"] == 0
