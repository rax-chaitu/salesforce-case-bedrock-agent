#!/usr/bin/env python3
"""
Dual-Mode Lambda Handler
- SQS events: Production flow from Salesforce Platform Events
- API Gateway: REST endpoints for testing

Event source detection routes to appropriate handler.
"""

import json
import logging
import os
import uuid
from datetime import datetime

from bedrock_client import BedrockAgentClient
from salesforce_client import SalesforceClient


class StructuredLogger:
    """JSON structured logging for CloudWatch Insights queries."""

    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

    def _log(self, level, event, **kwargs):
        msg = {"event": event, "timestamp": datetime.utcnow().isoformat(), **kwargs}
        getattr(self.logger, level)(json.dumps(msg))

    def info(self, event, **kwargs):
        self._log("info", event, **kwargs)

    def error(self, event, **kwargs):
        self._log("error", event, **kwargs)

    def warning(self, event, **kwargs):
        self._log("warning", event, **kwargs)


logger = StructuredLogger(__name__)

# Initialize clients
bedrock = BedrockAgentClient()
salesforce = SalesforceClient()


def lambda_handler(event, context):
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
# SQS EVENT HANDLER (Production Flow)
# =============================================================================


def handle_sqs_event(event):
    """
    Process SQS messages from EventBridge (Salesforce Platform Events).
    Returns batchItemFailures for partial batch failure handling.
    """
    results = []
    failed_items = []

    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            detail = body.get("detail", {})

            # Event Relay: detail.payload contains Platform Event fields
            event_payload = detail.get("payload", {})

            # Get Case ID from Platform Event Record_Id__c field
            case_id = event_payload.get("Record_Id__c")

            # Parse the nested Payload__c JSON string (contains actual case data)
            payload_str = event_payload.get("Payload__c", "{}")
            case_data = json.loads(payload_str) if payload_str else {}

            case_number = case_data.get("Case_Number__c", "")
            subject = case_data.get("Subject__c", "")
            description = case_data.get("Description__c", "")
            case_type = case_data.get("Type__c", "")
            priority = case_data.get("Priority__c", "Medium")

            if not case_id:
                logger.warning("case_skipped", reason="no_case_id")
                continue

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


def analyze_case(case_id, case_number, subject, description, case_type, priority):
    """
    Invoke Bedrock Agent to analyze case and return structured response.
    """
    prompt = f"""Analyze this Salesforce case and return JSON:

Case Number: {case_number}
Subject: {subject}
Description: {description}
Type: {case_type}
Priority: {priority}

Search Knowledge Base for similar cases and provide analysis as JSON."""

    session_id = f"case-{case_id}-{uuid.uuid4().hex[:8]}"

    response_text = bedrock.invoke_agent(prompt, session_id)

    # Parse JSON from response (agent should return structured JSON)
    try:
        # Try to extract JSON from response
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback: wrap text response in structure
        analysis = {
            "summary": response_text[:500],
            "steps": [],
            "self_resolvable": False,
            "similar_cases": [],
            "recommendation": response_text,
        }

    analysis["analyzed_date"] = datetime.utcnow().isoformat()
    return analysis


# =============================================================================
# API GATEWAY HANDLER (Testing Flow)
# =============================================================================


def handle_api_gateway(event):
    """
    Handle REST API requests for testing.

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

        request_data = {}
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                return create_response(400, {"error": "Invalid JSON"})

        # Route to handlers
        if path == "/health" and http_method == "GET":
            return handle_health()
        elif path == "/agent/invoke" and http_method == "POST":
            return handle_agent_invoke(request_data)
        elif path == "/case/analyze" and http_method == "POST":
            return handle_case_analyze(request_data)
        elif path == "/kb/search" and http_method == "POST":
            return handle_kb_search(request_data)
        else:
            return create_response(404, {"error": f"Not found: {http_method} {path}"})

    except Exception as e:
        logger.error("api_error", error=str(e), path=event.get("path"))
        return create_response(500, {"error": str(e)})


def create_response(status_code, body):
    """Create HTTP response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def handle_health():
    """Health check endpoint."""
    return create_response(
        200,
        {
            "status": "healthy",
            "service": "salesforceagent-dual-mode",
            "agent_id": os.environ.get("BEDROCK_AGENT_ID"),
            "salesforce_configured": salesforce.is_configured(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def handle_agent_invoke(request_data):
    """Direct agent invocation for testing."""
    if "prompt" not in request_data:
        return create_response(400, {"error": "Missing: prompt"})

    session_id = request_data.get("session_id") or str(uuid.uuid4())
    result = bedrock.invoke_agent(request_data["prompt"], session_id)

    return create_response(
        200,
        {
            "success": True,
            "response": result,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def handle_case_analyze(request_data):
    """Case analysis endpoint for testing."""
    required = ["case_number", "subject", "description"]
    for field in required:
        if field not in request_data:
            return create_response(400, {"error": f"Missing: {field}"})

    analysis = analyze_case(
        case_id=request_data.get("case_id", "test-" + uuid.uuid4().hex[:8]),
        case_number=request_data["case_number"],
        subject=request_data["subject"],
        description=request_data["description"],
        case_type=request_data.get("type", ""),
        priority=request_data.get("priority", "Medium"),
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
    )


def handle_kb_search(request_data):
    """Direct Knowledge Base search."""
    if "query" not in request_data:
        return create_response(400, {"error": "Missing: query"})

    results = bedrock.search_knowledge_base(
        request_data["query"], request_data.get("max_results", 5)
    )

    return create_response(
        200,
        {
            "success": True,
            "query": request_data["query"],
            "results": results,
            "result_count": len(results),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
