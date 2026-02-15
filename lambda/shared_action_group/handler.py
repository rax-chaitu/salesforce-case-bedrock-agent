"""
Shared Bedrock Agent Action Group - Generic Salesforce SOQL queries.
Routes: /querySalesforce
Reusable across all agents (Case, Opportunity, etc.).
Uses shared layers: rackspace_sf_auth (auth) + rackspace_sf_queries (query helpers)
"""

import json
import logging

from rackspace_sf_queries import query_sf

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Handle Bedrock Agent action group invocations."""
    api_path = event.get("apiPath", "")
    logger.info(json.dumps({"event": "shared_action_invoked", "api_path": api_path}))

    params = {}
    try:
        props = event.get("requestBody", {}).get("content", {}).get("application/json", {}).get("properties", [])
        for p in props:
            params[p["name"]] = p["value"]
    except (KeyError, TypeError):
        pass

    if api_path == "/querySalesforce":
        try:
            soql = params.get("soql", "")
            if not soql:
                body = json.dumps({"error": "No SOQL query provided", "records": []})
            else:
                result = query_sf(soql)
                body = json.dumps(result)
        except Exception as e:
            logger.error(f"Query error: {e}")
            body = json.dumps({"records": [], "total_found": 0, "error": str(e)})
    else:
        body = json.dumps({"error": f"Unknown path: {api_path}"})

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup", ""),
            "apiPath": api_path,
            "httpMethod": event.get("httpMethod", "POST"),
            "httpStatusCode": 200,
            "responseBody": {"application/json": {"body": body}},
        },
    }
