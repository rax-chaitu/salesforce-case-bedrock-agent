#!/usr/bin/env python3
"""
Dual-Mode Lambda Handler for Salesforce Case AI Analysis

PRODUCTION MODE (SQS):
    Salesforce Case → Platform Event → Event Relay → EventBridge → SQS → Lambda
    This is the primary production flow. Data is trusted from Salesforce.

DEVELOPMENT MODE (API Gateway):
    REST API endpoints for testing agent invocation, KB search, and case analysis.
    These endpoints are for DEVELOPMENT/TESTING ONLY and should be restricted
    or disabled in production.

Event source detection routes to appropriate handler.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from bedrock_client import BedrockAgentClient
from salesforce_client import SalesforceClient


# =============================================================================
# CONFIGURATION
# =============================================================================

# CORS: Restrict to specific domains (CRITICAL SECURITY FIX)
ALLOWED_ORIGINS = [
    # Add your Salesforce domain(s) here
    os.environ.get("ALLOWED_ORIGIN", "https://rax.my.salesforce.com"),
    "https://rax--inttest.sandbox.my.salesforce.com",
    "https://rax--uat.sandbox.my.salesforce.com",
]

# Input validation limits
MAX_SUBJECT_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 32000
MAX_PROMPT_LENGTH = 10000

# Salesforce ID pattern (15 or 18 character alphanumeric)
SALESFORCE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9]{15}([a-zA-Z0-9]{3})?$")


class StructuredLogger:
    """JSON structured logging for CloudWatch Insights queries."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

    def _log(self, level: str, event: str, **kwargs: Any) -> None:
        msg = {"event": event, "timestamp": datetime.utcnow().isoformat(), **kwargs}
        getattr(self.logger, level)(json.dumps(msg))

    def info(self, event: str, **kwargs: Any) -> None:
        self._log("info", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log("error", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log("warning", event, **kwargs)


logger = StructuredLogger(__name__)

# Lazy initialization for clients (reduces cold start impact)
_bedrock: Optional[BedrockAgentClient] = None
_salesforce: Optional[SalesforceClient] = None


def get_bedrock_client() -> BedrockAgentClient:
    """Lazy initialization of Bedrock client."""
    global _bedrock
    if _bedrock is None:
        _bedrock = BedrockAgentClient()
    return _bedrock


def get_salesforce_client() -> SalesforceClient:
    """Lazy initialization of Salesforce client."""
    global _salesforce
    if _salesforce is None:
        _salesforce = SalesforceClient()
    return _salesforce


# =============================================================================
# INPUT VALIDATION (SECURITY FIX)
# =============================================================================


def validate_salesforce_id(case_id: str) -> bool:
    """Validate Salesforce ID format to prevent injection attacks."""
    if not case_id:
        return False
    return bool(SALESFORCE_ID_PATTERN.match(case_id))


def sanitize_string(value: str, max_length: int, field_name: str) -> str:
    """Sanitize and truncate string input."""
    if not isinstance(value, str):
        value = str(value) if value else ""
    # Truncate to max length
    if len(value) > max_length:
        logger.warning("input_truncated", field=field_name, original_length=len(value), max_length=max_length)
        value = value[:max_length]
    return value


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Main entry point - detects event source and routes accordingly.

    SQS Event structure: {"Records": [{"body": "...", "eventSource": "aws:sqs"}]}
    API Gateway structure: {"httpMethod": "...", "path": "...", "body": "..."}
    """
    # Detect event source
    if event.get("Records"):
        first_record = event["Records"][0]
        if first_record.get("eventSource") == "aws:sqs":
            return handle_sqs_event(event)

    # Default to API Gateway
    return handle_api_gateway(event)


# =============================================================================
# SQS EVENT HANDLER (PRODUCTION)
# =============================================================================
# This is the PRIMARY production handler. Cases flow from:
# Salesforce Case → Platform Event → Event Relay → EventBridge → SQS → Lambda
# =============================================================================


def handle_sqs_event(event: dict) -> dict:
    """
    Process SQS messages from EventBridge (Salesforce Platform Events).
    Returns batchItemFailures for partial batch failure handling.
    
    NOTE: Data comes from trusted Salesforce Platform Events via Event Relay,
    so no input sanitization needed here.
    """
    results = []
    failed_items = []
    salesforce = get_salesforce_client()

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            detail = body.get("detail", {})

            # Event Relay: detail.payload contains Platform Event fields
            event_payload = detail.get("payload", {})

            # Get Case ID from Platform Event Record_Id__c field
            case_id = event_payload.get("Record_Id__c", "")

            if not case_id:
                logger.warning("case_skipped", reason="no_case_id")
                continue

            # Parse the nested Payload__c JSON string (contains actual case data)
            payload_str = event_payload.get("Payload__c", "{}")
            case_data = json.loads(payload_str) if payload_str else {}

            # Trusted data from Salesforce Platform Events - no sanitization needed
            case_number = case_data.get("Case_Number__c", "")
            subject = case_data.get("Subject", "")
            description = case_data.get("Description", "")

            # Idempotency check: skip if already analyzed today
            if salesforce.is_configured() and salesforce.is_already_analyzed(case_id):
                logger.info("case_skipped", reason="already_analyzed_today", case_id=case_id)
                continue

            logger.info("case_processing_started", case_id=case_id, case_number=case_number)

            # Analyze case with Bedrock Agent
            analysis = analyze_case(case_id=case_id, case_data=case_data)

            # Update Salesforce Case with analysis
            if salesforce.is_configured():
                salesforce.update_case_analysis(case_id, analysis)
                logger.info("case_updated", case_id=case_id, case_number=case_number)
            else:
                logger.warning("salesforce_not_configured", case_id=case_id)

            results.append(
                {
                    "case_id": case_id,
                    "case_number": case_number,
                    "status": "processed",
                    "self_resolvable": analysis.get("self_resolvable", False),
                }
            )

        except Exception as e:
            logger.error("case_processing_failed", error=str(e), message_id=record.get("messageId"))
            failed_items.append({"itemIdentifier": record["messageId"]})

    # Return failed items for SQS to retry
    if failed_items:
        return {"batchItemFailures": failed_items}

    return {
        "statusCode": 200,
        "body": json.dumps({"processed": len(results), "results": results}),
    }


def analyze_case(case_id: str, case_data: dict) -> dict:
    """
    Invoke Bedrock Agent to analyze case and return structured response.
    Sends full case payload as JSON — agent interprets field names directly.
    """
    bedrock = get_bedrock_client()

    # Pre-compute search hints so agent doesn't waste LLM calls figuring them out
    subject = case_data.get("Subject", case_data.get("Subject__c", ""))
    support_reason = case_data.get("Support_Reason__c", "")
    tool = case_data.get("Tool__c", case_data.get("Tool", ""))
    keywords = " ".join(w for w in subject.split()[:5] if len(w) > 2)

    logger.info({"event": "analyze_start", "case_id": case_id, "subject": subject,
                 "support_reason": support_reason, "tool": tool, "keywords": keywords})

    # Deterministic KA search — agent picks bad keywords, so we do it ourselves
    ka_titles = []
    try:
        sf = get_salesforce_client()
        if sf.is_configured():
            # Use subject + support_reason + tool for broad KA search
            search_words = set()
            for text in [subject, support_reason, tool]:
                search_words.update(w for w in re.findall(r'\w+', text.replace("-", " ").replace("/", " ")) if len(w) > 3)
            like_clauses = [f"Title LIKE '%{w}%'" for w in list(search_words)[:8]]
            if like_clauses:
                kav_query = (
                    f"SELECT Title FROM KnowledgeArticleVersion "
                    f"WHERE PublishStatus = 'Online' AND Language = 'en_US' "
                    f"AND ({' OR '.join(like_clauses)}) LIMIT 10"
                )
                kav_results = sf.query(kav_query)
                ka_titles = [r.get("Title", "") for r in kav_results.get("records", []) if r.get("Title")]
                logger.info({"event": "ka_search_deterministic", "count": len(ka_titles), "titles": ka_titles})
    except Exception as e:
        logger.warning("ka_search_failed", error=str(e))

    prompt = f"""Analyze this Salesforce case. Use these search parameters:
- searchSimilarCases: keywords="{keywords}", support_reason="{support_reason}", tool="{tool}"
- searchKnowledgeArticles: keywords="{keywords}"

Case data:
{json.dumps(case_data, indent=2, default=str)}

Search the SOP Knowledge Base first, then call searchSimilarCases, then call searchKnowledgeArticles, then return your analysis as JSON.
ALL of these JSON fields are REQUIRED in your response — do not skip any:
- "summary": 2-3 sentence analysis of what is being requested and why
- "category": Opportunity | User_Access | Account | Data_Update | Pricing | Configuration | Integration | Other
- "severity": Critical | High | Medium | Low
- "root_cause": what triggered this request
- "admin_steps": steps a Salesforce admin takes to resolve this (navigation paths, buttons, fields)
- "user_steps": steps the end user can do themselves based on the SOP Knowledge Base (e.g. submit request, click Request Access, navigate to record). NEVER include "create a case" or "submit a case" — the case already exists. If there are no real self-service steps, return an empty array [].
- "similar_cases": case numbers from searchSimilarCases
- "kb_articles": SOP document names and Knowledge Article titles
- "estimated_resolution": time estimate with brief explanation
- "recommendation": specific action needed
- "self_resolvable": true if user can self-service, false if admin-only"""

    session_id = f"case-{case_id}-{uuid.uuid4().hex[:8]}"

    response_text = bedrock.invoke_agent(prompt, session_id)

    logger.info({"event": "agent_raw_response", "case_id": case_id,
                 "response_length": len(response_text), "response_preview": response_text[:2000]})
    # Detect guardrail-blocked responses (input or output)
    guardrail_phrases = [
        "I cannot provide that information",  # blocked output
        "I can only help with Salesforce case analysis",  # blocked input
    ]
    if any(phrase.lower() in response_text.lower() for phrase in guardrail_phrases):
        logger.warning(f"Guardrail blocked agent output for case {case_id}", response_preview=response_text[:300])
        return {
            "summary": (
                "AI analysis was partially blocked by content safety guardrails. "
                "The case may contain content that triggered automated filtering. "
                "Please review the case manually."
            ),
            "steps": ["1. Review the case description and comments manually.",
                      "2. If this is a false positive, re-run analysis after editing sensitive content."],
            "self_resolvable": False,
            "similar_cases": [],
            "kb_articles": [],
            "recommendation": "Manual review required — guardrail content filter triggered on agent output.",
            "guardrail_blocked": True,
            "analyzed_date": datetime.utcnow().isoformat(),
        }

    # Parse JSON from response (agent should return structured JSON)
    try:
        # Try to extract JSON from response
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        analysis = None
        # Try markdown code block first, then raw JSON object
        json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            try:
                analysis = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        if not analysis:
            analysis = {
                "summary": response_text[:500],
                "steps": [],
                "self_resolvable": False,
                "similar_cases": [],
                "kb_articles": [],
                "recommendation": response_text,
            }

    # Post-process: merge deterministic KA titles with agent's kb_articles
    agent_articles = analysis.get("kb_articles", [])

    logger.info({"event": "agent_parsed", "case_id": case_id,
                 "fields": list(analysis.keys()),
                 "similar_cases_count": len(analysis.get("similar_cases", [])),
                 "similar_cases": analysis.get("similar_cases", []),
                 "agent_kb_articles": agent_articles,
                 "admin_steps_count": len(analysis.get("admin_steps", [])),
                 "user_steps_count": len(analysis.get("user_steps", [])),
                 "self_resolvable": analysis.get("self_resolvable")})
    # Combine: deterministic KA titles + agent's articles, dedupe (case-insensitive)
    seen_lower = set()
    all_articles = []
    for t in list(ka_titles) + [a if isinstance(a, str) else str(a) for a in agent_articles]:
        if t.lower() not in seen_lower:
            seen_lower.add(t.lower())
            all_articles.append(t)
    # Score by subject + description keyword overlap
    if all_articles:
        desc_text = case_data.get("Description", case_data.get("Description__c", ""))
        combined = f"{subject} {desc_text} {support_reason}"
        case_words = {w.lower() for w in re.findall(r'\w+', combined) if len(w) >= 3}
        scored = []
        for article in all_articles:
            title_words = {w.lower() for w in re.findall(r'\w+', article) if len(w) >= 3}
            score = len(case_words & title_words)
            if score >= 2:
                scored.append((score, article))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            analysis["kb_articles"] = [a for _, a in scored[:5]]
        elif all_articles:
            # Nothing scored 2+, keep top 3 with 1+ match
            fallback = [(len(case_words & {w.lower() for w in re.findall(r'\w+', a) if len(w) >= 3}), a)
                        for a in all_articles]
            fallback = [(s, a) for s, a in fallback if s >= 1]
            fallback.sort(key=lambda x: x[0], reverse=True)
            analysis["kb_articles"] = [a for _, a in fallback[:3]]

    # Post-process: merge admin_steps + user_steps into single steps field for SF
    admin_steps = analysis.get("admin_steps", [])
    user_steps = analysis.get("user_steps", [])
    existing_steps = analysis.get("steps", [])

    # Strip user_steps that are just "create/submit a case" — circular advice
    if user_steps:
        case_submission_phrases = ["create a new case", "submit the case", "create a case",
                                   "open a case", "save and submit", "submit a case"]
        filtered = [s for s in user_steps if not any(
            p in str(s).lower() for p in case_submission_phrases)]
        if len(filtered) < len(user_steps):
            logger.info({"event": "user_steps_filtered", "case_id": case_id,
                         "original": len(user_steps), "kept": len(filtered)})
            user_steps = filtered

    if admin_steps or user_steps:
        merged = []
        if admin_steps:
            merged.append("ADMIN STEPS:")
            merged.extend(str(s) for s in admin_steps)
        if user_steps:
            merged.append("USER SELF-SERVICE STEPS:")
            merged.extend(str(s) for s in user_steps)
        analysis["steps"] = merged
        if user_steps:
            analysis["self_resolvable"] = True
    elif existing_steps:
        # Agent didn't use separate fields — check if user steps are missing
        steps_text = " ".join(str(s) for s in existing_steps).lower()
        has_self_service = any(p in steps_text for p in ["self-service", "self service", "yourself", "submit a request", "request form", "user step"])
        if not has_self_service:
            analysis["steps"] = (
                ["ADMIN STEPS:"] + existing_steps +
                ["USER SELF-SERVICE: Check the related Knowledge Article for self-service options."]
            )

    analysis["analyzed_date"] = datetime.utcnow().isoformat()
    analysis["_real_ka_titles"] = [t.lower() for t in ka_titles]  # for hyperlink check

    logger.info({"event": "analyze_complete", "case_id": case_id,
                 "final_kb_articles": analysis.get("kb_articles", []),
                 "final_similar_cases": analysis.get("similar_cases", []),
                 "final_steps_count": len(analysis.get("steps", [])),
                 "self_resolvable": analysis.get("self_resolvable"),
                 "has_summary": bool(analysis.get("summary")),
                 "has_category": bool(analysis.get("category")),
                 "has_severity": bool(analysis.get("severity"))})

    return analysis


# =============================================================================
# API GATEWAY HANDLER (DEVELOPMENT/TESTING ONLY)
# =============================================================================
# NOTE: The API Gateway endpoints below are for DEVELOPMENT and TESTING only.
# In PRODUCTION, only the SQS handler (Platform Events) is used.
# The API Gateway can be disabled in production by removing the API Gateway
# Terraform resources or restricting access via IAM policies.
# =============================================================================


def handle_api_gateway(event: dict) -> dict:
    """
    Handle REST API requests for DEVELOPMENT/TESTING only.

    Endpoints:
    - GET  /health        - Health check
    - POST /agent/invoke  - Direct agent invocation
    - POST /case/analyze  - Case analysis
    - POST /kb/search     - Knowledge Base search
    """
    try:
        http_method = event.get("httpMethod", "GET")
        path = event.get("path", "/")
        body = event.get("body", "")
        
        # Get origin for CORS
        headers = event.get("headers", {}) or {}
        origin = headers.get("origin") or headers.get("Origin", "")

        request_data = {}
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {"error": "Invalid JSON"}, origin)

        # Route to handlers
        if path == "/health" and http_method == "GET":
            return handle_health(origin)
        elif path == "/agent/invoke" and http_method == "POST":
            return handle_agent_invoke(request_data, origin)
        elif path == "/case/analyze" and http_method == "POST":
            return handle_case_analyze(request_data, origin)
        elif path == "/kb/search" and http_method == "POST":
            return handle_kb_search(request_data, origin)
        else:
            return create_response(404, {"error": f"Not found: {http_method} {path}"}, origin)

    except Exception as e:
        logger.error("api_error", error=str(e), path=event.get("path"))
        return create_response(500, {"error": str(e)}, origin if "origin" in locals() else "")


def get_cors_origin(request_origin: str) -> str:
    """
    Return allowed CORS origin. Only allows configured domains.
    CRITICAL SECURITY: Prevents CSRF attacks by restricting cross-origin requests.
    """
    if request_origin in ALLOWED_ORIGINS:
        return request_origin
    # Default to first allowed origin if request origin not in list
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else ""


def create_response(status_code: int, body: dict, request_origin: str = "") -> dict:
    """Create HTTP response with restricted CORS headers."""
    cors_origin = get_cors_origin(request_origin)
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Credentials": "true",
        },
        "body": json.dumps(body, default=str),
    }


def handle_health(origin: str = "") -> dict:
    """Health check endpoint."""
    salesforce = get_salesforce_client()
    health = {
        "status": "healthy",
        "service": "sf-case-processor",
        "agent_id": os.environ.get("BEDROCK_AGENT_ID"),
        "salesforce_configured": salesforce.is_configured(),
        "timestamp": datetime.utcnow().isoformat(),
    }
    if salesforce.is_configured():
        sf_status = salesforce.check_connection()
        health["salesforce_connected"] = sf_status["connected"]
        if sf_status.get("instance_url"):
            health["salesforce_instance"] = sf_status["instance_url"]
        if sf_status.get("error"):
            health["salesforce_error"] = sf_status["error"]
    return create_response(200, health, origin)


def handle_agent_invoke(request_data: dict, origin: str = "") -> dict:
    """Direct agent invocation for testing."""
    if "prompt" not in request_data:
        return create_response(400, {"error": "Missing: prompt"}, origin)

    # SECURITY: Validate and sanitize prompt
    prompt = sanitize_string(request_data["prompt"], MAX_PROMPT_LENGTH, "prompt")
    if not prompt:
        return create_response(400, {"error": "Empty prompt"}, origin)

    bedrock = get_bedrock_client()
    session_id = request_data.get("session_id") or str(uuid.uuid4())
    result = bedrock.invoke_agent(prompt, session_id)

    return create_response(
        200,
        {
            "success": True,
            "response": result,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
        origin,
    )


def handle_case_analyze(request_data: dict, origin: str = "") -> dict:
    """Case analysis endpoint for testing."""
    required = ["case_number", "subject", "description"]
    for field in required:
        if field not in request_data:
            return create_response(400, {"error": f"Missing: {field}"}, origin)

    # SECURITY: Sanitize inputs
    case_id = request_data.get("case_id", "")
    if case_id and not validate_salesforce_id(case_id):
        case_id = "test-" + uuid.uuid4().hex[:8]
    elif not case_id:
        case_id = "test-" + uuid.uuid4().hex[:8]

    # Sanitize all string values for API input
    case_data = {}
    for key, value in request_data.items():
        if key == "case_id":
            continue
        if isinstance(value, str):
            case_data[key] = sanitize_string(value, MAX_DESCRIPTION_LENGTH, key)
        else:
            case_data[key] = value

    analysis = analyze_case(case_id=case_id, case_data=case_data)

    return create_response(
        200,
        {
            "success": True,
            "case": {
                "number": request_data["case_number"],
                "subject": request_data["subject"],
                "priority": request_data.get("priority", "Medium"),
            },
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat(),
        },
        origin,
    )


def handle_kb_search(request_data: dict, origin: str = "") -> dict:
    """Direct Knowledge Base search."""
    if "query" not in request_data:
        return create_response(400, {"error": "Missing: query"}, origin)

    # SECURITY: Sanitize query
    query = sanitize_string(request_data["query"], MAX_PROMPT_LENGTH, "query")
    if not query:
        return create_response(400, {"error": "Empty query"}, origin)

    bedrock = get_bedrock_client()
    max_results = min(int(request_data.get("max_results", 5)), 20)  # Cap at 20
    
    results = bedrock.search_knowledge_base(query, max_results)

    return create_response(
        200,
        {
            "success": True,
            "query": query,
            "results": results,
            "result_count": len(results),
            "timestamp": datetime.utcnow().isoformat(),
        },
        origin,
    )
