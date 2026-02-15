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
            case_type = case_data.get("Type", "")
            priority = case_data.get("Priority", "Medium")
            tool = case_data.get("Tool__c", "")
            support_reason = case_data.get("Support_Reason__c", "")
            reason = case_data.get("Reason", "")
            record_type = case_data.get("Record_Type__c", "")
            status = case_data.get("Status", "")
            origin = case_data.get("Origin", "")
            root_cause = case_data.get("Root_Cause_of_Inquiry__c", "")
            case_type_detail = case_data.get("Case_Type__c", "")
            department = case_data.get("Department__c", "")
            segment = case_data.get("Segment__c", "")
            opp_number = case_data.get("OpportunityNumber__c", "")

            # Idempotency check: skip if already analyzed today
            if salesforce.is_configured() and salesforce.is_already_analyzed(case_id):
                logger.info("case_skipped", reason="already_analyzed_today", case_id=case_id)
                continue

            logger.info("case_processing_started", case_id=case_id, case_number=case_number)

            # Analyze case with Bedrock Agent
            analysis = analyze_case(
                case_id=case_id,
                case_number=case_number,
                subject=subject,
                description=description,
                case_type=case_type,
                priority=priority,
                tool=tool,
                support_reason=support_reason,
                reason=reason,
                record_type=record_type,
                status=status,
                origin=origin,
                root_cause=root_cause,
                case_type_detail=case_type_detail,
                department=department,
                segment=segment,
                opp_number=opp_number,
            )

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


def analyze_case(
    case_id: str, case_number: str, subject: str, description: str, case_type: str, priority: str,
    tool: str = "", support_reason: str = "", reason: str = "", record_type: str = "",
    status: str = "", origin: str = "", root_cause: str = "", case_type_detail: str = "",
    department: str = "", segment: str = "", opp_number: str = ""
) -> dict:
    """
    Invoke Bedrock Agent to analyze case and return structured response.
    
    NOTE: Input sanitization is handled by callers (API handlers sanitize, SQS handler trusts SF data).
    """
    bedrock = get_bedrock_client()
    
    # Build context lines, only include non-empty fields
    fields = [
        f"Case Number: {case_number}",
        f"Subject: {subject}",
        f"Description: {description}",
        f"Type: {case_type}",
        f"Priority: {priority}",
    ]
    optional = [
        ("Tool", tool),
        ("Support Reason", support_reason),
        ("Case Reason", reason),
        ("What Needs Updated", record_type),
        ("Status", status),
        ("Origin", origin),
        ("Root Cause of Inquiry", root_cause),
        ("Case Type", case_type_detail),
        ("Department", department),
        ("Segment", segment),
        ("Opportunity Number", opp_number),
    ]
    for label, value in optional:
        if value:
            fields.append(f"{label}: {value}")

    case_context = "\n".join(fields)

    prompt = f"""Search the Knowledge Base for articles and resolved cases related to this case, then search for similar closed cases using the searchSimilarCases action, then analyze it:

{case_context}

Base your analysis and recommendations on Knowledge Base content. If KB articles describe specific tools, processes, or self-service options for this type of request, include those details in your response. Include any similar closed cases found in the similar_cases array."""

    session_id = f"case-{case_id}-{uuid.uuid4().hex[:8]}"

    response_text = bedrock.invoke_agent(prompt, session_id)

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

    analysis["analyzed_date"] = datetime.utcnow().isoformat()
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
        "service": "salesforceagent-dual-mode",
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

    analysis = analyze_case(
        case_id=case_id,
        case_number=sanitize_string(request_data["case_number"], 20, "case_number"),
        subject=sanitize_string(request_data["subject"], MAX_SUBJECT_LENGTH, "subject"),
        description=sanitize_string(request_data["description"], MAX_DESCRIPTION_LENGTH, "description"),
        case_type=sanitize_string(request_data.get("type", ""), 100, "type"),
        priority=sanitize_string(request_data.get("priority", "Medium"), 20, "priority"),
        tool=sanitize_string(request_data.get("tool", ""), 100, "tool"),
        support_reason=sanitize_string(request_data.get("support_reason", ""), 200, "support_reason"),
        reason=sanitize_string(request_data.get("reason", ""), 200, "reason"),
        record_type=sanitize_string(request_data.get("record_type", ""), 100, "record_type"),
        status=sanitize_string(request_data.get("status", ""), 50, "status"),
        origin=sanitize_string(request_data.get("origin", ""), 50, "origin"),
        root_cause=sanitize_string(request_data.get("root_cause", ""), 200, "root_cause"),
        case_type_detail=sanitize_string(request_data.get("case_type_detail", ""), 100, "case_type_detail"),
        department=sanitize_string(request_data.get("department", ""), 100, "department"),
        segment=sanitize_string(request_data.get("segment", ""), 100, "segment"),
        opp_number=sanitize_string(request_data.get("opp_number", ""), 50, "opp_number"),
    )

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
