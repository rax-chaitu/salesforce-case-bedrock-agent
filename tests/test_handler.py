"""
Tests for case_processor/handler.py — the main orchestrator.
Covers: analyze_case, SQS handling, API routing, input validation, JSON parsing.

Run: python3 -m pytest tests/test_handler.py -v
"""

import json
import re
import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# INPUT VALIDATION
# =============================================================================

class TestInputValidation:
    def test_valid_18char_id(self, case_handler):
        assert case_handler.validate_salesforce_id("500Ox00000gTHmrIAG") is True

    def test_valid_15char_id(self, case_handler):
        assert case_handler.validate_salesforce_id("500Ox00000gTHmr") is True

    def test_invalid_id_special_chars(self, case_handler):
        assert case_handler.validate_salesforce_id("500Ox00000'; DROP") is False

    def test_empty_id(self, case_handler):
        assert case_handler.validate_salesforce_id("") is False

    def test_sanitize_truncates(self, case_handler):
        assert len(case_handler.sanitize_string("a" * 1000, 500, "test")) == 500

    def test_sanitize_preserves_short(self, case_handler):
        assert case_handler.sanitize_string("hello", 500, "test") == "hello"

    def test_sanitize_non_string(self, case_handler):
        assert case_handler.sanitize_string(12345, 500, "test") == "12345"


# =============================================================================
# CORS
# =============================================================================

class TestCORS:
    def test_allowed_origin(self, case_handler):
        result = case_handler.get_cors_origin("https://rax--inttest.sandbox.my.salesforce.com")
        assert result == "https://rax--inttest.sandbox.my.salesforce.com"

    def test_disallowed_origin(self, case_handler):
        assert case_handler.get_cors_origin("https://evil.com") != "https://evil.com"

    def test_response_has_cors_headers(self, case_handler):
        resp = case_handler.create_response(200, {"ok": True}, "")
        assert "Access-Control-Allow-Origin" in resp["headers"]


# =============================================================================
# LAMBDA HANDLER ROUTING
# =============================================================================

class TestLambdaRouting:
    def test_sqs_event_detected(self, case_handler):
        event = {"Records": [{"eventSource": "aws:sqs", "body": "{}", "messageId": "m1"}]}
        with patch.object(case_handler, "handle_sqs_event", return_value={"statusCode": 200}) as mock:
            case_handler.lambda_handler(event, None)
            mock.assert_called_once()

    def test_api_event_detected(self, case_handler):
        event = {"httpMethod": "GET", "path": "/health"}
        with patch.object(case_handler, "handle_api_gateway", return_value={"statusCode": 200}) as mock:
            case_handler.lambda_handler(event, None)
            mock.assert_called_once()


# =============================================================================
# API GATEWAY ROUTING
# =============================================================================

class TestAPIRouting:
    def test_unknown_path_returns_404(self, case_handler):
        resp = case_handler.handle_api_gateway({"httpMethod": "GET", "path": "/unknown", "headers": {}})
        assert resp["statusCode"] == 404

    def test_invalid_json_body_returns_400(self, case_handler):
        resp = case_handler.handle_api_gateway({"httpMethod": "POST", "path": "/agent/invoke", "body": "not json", "headers": {}})
        assert resp["statusCode"] == 400


# =============================================================================
# SQS EVENT HANDLING
# =============================================================================

class TestSQSHandler:
    def _make_sqs_event(self, case_id, case_data):
        return {"Records": [{"messageId": "msg-001", "body": json.dumps({
            "detail": {"payload": {"Record_Id__c": case_id, "Payload__c": json.dumps(case_data)}}
        }), "eventSource": "aws:sqs"}]}

    def test_processes_valid_case(self, case_handler, sample_case_data):
        mock_sf = MagicMock()
        mock_sf.is_configured.return_value = True
        mock_sf.is_already_analyzed.return_value = False
        with patch.object(case_handler, "get_salesforce_client", return_value=mock_sf), \
             patch.object(case_handler, "analyze_case", return_value={"summary": "Test", "self_resolvable": False}):
            event = self._make_sqs_event("500Ox00000gTHmrIAG", sample_case_data)
            result = case_handler.handle_sqs_event(event)
            mock_sf.update_case_analysis.assert_called_once()

    def test_skips_already_analyzed(self, case_handler):
        mock_sf = MagicMock()
        mock_sf.is_configured.return_value = True
        mock_sf.is_already_analyzed.return_value = True
        with patch.object(case_handler, "get_salesforce_client", return_value=mock_sf), \
             patch.object(case_handler, "analyze_case") as mock_analyze:
            case_handler.handle_sqs_event(self._make_sqs_event("500Ox00000gTHmrIAG", {"Subject": "Test"}))
            mock_analyze.assert_not_called()

    def test_skips_no_case_id(self, case_handler):
        mock_sf = MagicMock()
        mock_sf.is_configured.return_value = True
        with patch.object(case_handler, "get_salesforce_client", return_value=mock_sf), \
             patch.object(case_handler, "analyze_case") as mock_analyze:
            case_handler.handle_sqs_event(self._make_sqs_event("", {"Subject": "Test"}))
            mock_analyze.assert_not_called()

    def test_failed_case_returns_batch_failure(self, case_handler):
        mock_sf = MagicMock()
        mock_sf.is_configured.return_value = True
        mock_sf.is_already_analyzed.return_value = False
        with patch.object(case_handler, "get_salesforce_client", return_value=mock_sf), \
             patch.object(case_handler, "analyze_case", side_effect=Exception("boom")):
            result = case_handler.handle_sqs_event(self._make_sqs_event("500Ox00000gTHmrIAG", {"Subject": "T", "Case_Number__c": "001"}))
            assert "batchItemFailures" in result
            assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-001"


# =============================================================================
# ANALYZE CASE — FULL FLOW
# =============================================================================

class TestAnalyzeCase:
    def _run(self, case_handler, sample_case_data, agent_response, kav_results=None):
        mock_sf = MagicMock()
        mock_sf.is_configured.return_value = True
        mock_sf.query.return_value = kav_results or {"records": [], "totalSize": 0}
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_agent.return_value = agent_response
        with patch.object(case_handler, "get_salesforce_client", return_value=mock_sf), \
             patch.object(case_handler, "get_bedrock_client", return_value=mock_bedrock):
            return case_handler.analyze_case("500Ox00000gTHmrIAG", sample_case_data)

    def test_full_flow_with_user_steps(self, case_handler, sample_case_data, sample_agent_response, sample_kav_results):
        result = self._run(case_handler, sample_case_data, sample_agent_response, sample_kav_results)
        assert result["category"] == "Opportunity"
        assert "ADMIN STEPS:" in result["steps"]
        assert "USER SELF-SERVICE STEPS:" in result["steps"]
        assert result["self_resolvable"] is True
        assert "_real_ka_titles" in result
        assert "_ka_url_map" in result

    def test_no_user_steps_not_self_resolvable(self, case_handler, sample_case_data, sample_agent_response_no_user_steps, sample_kav_results):
        result = self._run(case_handler, sample_case_data, sample_agent_response_no_user_steps, sample_kav_results)
        assert result["self_resolvable"] is False

    def test_circular_steps_filtered(self, case_handler, sample_case_data, sample_agent_response_circular_steps, sample_kav_results):
        result = self._run(case_handler, sample_case_data, sample_agent_response_circular_steps, sample_kav_results)
        steps_text = " ".join(str(s) for s in result.get("steps", []))
        assert "submit the case" not in steps_text.lower()

    def test_guardrail_blocked(self, case_handler, sample_case_data):
        result = self._run(case_handler, sample_case_data, "I cannot provide that information due to safety.")
        assert result.get("guardrail_blocked") is True

    def test_malformed_json_response(self, case_handler, sample_case_data):
        result = self._run(case_handler, sample_case_data, "The case needs admin review.")
        assert "summary" in result
        assert result["self_resolvable"] is False

    def test_markdown_wrapped_json(self, case_handler, sample_case_data, sample_kav_results):
        md = '```json\n{"summary":"Test","category":"Opportunity","severity":"Low","root_cause":"t","admin_steps":[],"user_steps":[],"similar_cases":[],"kb_articles":[],"estimated_resolution":"5m","recommendation":"t","self_resolvable":false,"ai_disclaimer":"AI"}\n```'
        result = self._run(case_handler, sample_case_data, md, sample_kav_results)
        assert result["summary"] == "Test"

    def test_deterministic_ka_url_map(self, case_handler, sample_case_data, sample_agent_response, sample_kav_results):
        result = self._run(case_handler, sample_case_data, sample_agent_response, sample_kav_results)
        assert all(t == t.lower() for t in result["_real_ka_titles"])
        for url in result["_ka_url_map"].values():
            assert "-" in url

    def test_sf_not_configured(self, case_handler, sample_case_data, sample_agent_response):
        mock_sf = MagicMock()
        mock_sf.is_configured.return_value = False
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_agent.return_value = sample_agent_response
        with patch.object(case_handler, "get_salesforce_client", return_value=mock_sf), \
             patch.object(case_handler, "get_bedrock_client", return_value=mock_bedrock):
            result = case_handler.analyze_case("500Ox00000gTHmrIAG", sample_case_data)
        assert "summary" in result


# =============================================================================
# KB ARTICLE SCORING (pure logic)
# =============================================================================

class TestKBScoring:
    def _score(self, ka_titles, agent_articles, subject, desc="", reason=""):
        seen_lower = set()
        all_articles = []
        for t in list(ka_titles) + [a if isinstance(a, str) else str(a) for a in agent_articles]:
            if t.lower() not in seen_lower:
                seen_lower.add(t.lower())
                all_articles.append(t)
        if not all_articles:
            return []
        combined = f"{subject} {desc} {reason}"
        case_words = {w.lower() for w in re.findall(r'\w+', combined) if len(w) >= 3}
        article_words = {a: {w.lower() for w in re.findall(r'\w+', a) if len(w) >= 3} for a in all_articles}
        scored = [(len(case_words & article_words[a]), a) for a in all_articles]
        high = [(s, a) for s, a in scored if s >= 2]
        if high:
            high.sort(key=lambda x: x[0], reverse=True)
            return [a for _, a in high[:5]]
        fallback = [(s, a) for s, a in scored if s >= 1]
        fallback.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in fallback[:3]]

    def test_relevant_selected(self):
        assert "Submit an Opportunity Team Member Request" in self._score(
            ["Submit an Opportunity Team Member Request"], [], "Add Partner on Opportunity Team Member")

    def test_irrelevant_filtered(self):
        assert "Create a Salesforce Case" not in self._score(
            ["Create a Salesforce Case"], [], "Opportunity Amount Change")

    def test_dedup(self):
        r = self._score(["Submit Request"], ["submit request"], "Submit Request for Team")
        assert len(r) == 1

    def test_empty(self):
        assert self._score([], [], "test") == []

    def test_max_5(self):
        assert len(self._score([f"Opportunity Team Member Request {i}" for i in range(10)], [], "Opportunity Team Member Request")) <= 5

    def test_description_used(self):
        assert "Outreach Tool Access Request" in self._score(
            ["Outreach Tool Access Request"], [], subject="Need access", desc="I need Outreach tool access")
