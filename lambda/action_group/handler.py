"""
Bedrock Agent Action Group - Search Salesforce for similar closed cases.
Auth from shared Lambda Layer: rackspace_sf_auth
"""

import json
import logging

from rackspace_sf_auth import SalesforceAuthClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_sf_auth = None


def get_sf():
    """Lazy init SF connection from shared auth layer."""
    global _sf_auth
    if _sf_auth is None:
        _sf_auth = SalesforceAuthClient()
    return _sf_auth.get_connection()


def search_similar_cases(params):
    """Search SF for similar closed cases by keywords and support reason."""
    keywords = params.get("keywords", "")
    support_reason = params.get("support_reason", "")
    max_results = min(int(params.get("max_results", 5)), 10)

    conditions = ["Status IN ('Closed', 'Closed Resolved')"]
    for word in keywords.split()[:3]:
        safe = word.replace("'", "\\'")
        conditions.append(f"Subject LIKE '%{safe}%'")
    if support_reason:
        safe_reason = support_reason.replace("'", "\\'")
        conditions.append(f"Support_Reason__c = '{safe_reason}'")

    where = " AND ".join(conditions)
    query = (
        f"SELECT Id, CaseNumber, Subject, Support_Reason__c, Description, "
        f"Case_Closure_Notes__c, ClosedDate "
        f"FROM Case WHERE {where} "
        f"ORDER BY ClosedDate DESC NULLS LAST LIMIT {max_results}"
    )

    logger.info(json.dumps({"event": "soql_query", "query": query}))
    sf = get_sf()
    results = sf.query(query)
    records = results.get("records", [])

    cases = []
    for r in records:
        case_id = r.get("Id", "")
        comments = ""
        if case_id:
            try:
                cr = sf.query(
                    f"SELECT CommentBody FROM CaseComment "
                    f"WHERE ParentId = '{case_id}' "
                    f"ORDER BY CreatedDate DESC LIMIT 3"
                )
                comments = " | ".join(
                    c.get("CommentBody", "") for c in cr.get("records", []) if c.get("CommentBody")
                )
            except Exception:
                pass

        cases.append({
            "case_number": r.get("CaseNumber", ""),
            "subject": r.get("Subject", ""),
            "support_reason": r.get("Support_Reason__c", ""),
            "description": (r.get("Description") or "")[:500],
            "closure_notes": r.get("Case_Closure_Notes__c") or "",
            "comments": comments[:500],
            "closed_date": r.get("ClosedDate") or "",
        })

    return {"cases": cases, "total_found": results.get("totalSize", 0)}


def lambda_handler(event, context):
    """Handle Bedrock Agent action group invocations."""
    api_path = event.get("apiPath", "")
    logger.info(json.dumps({"event": "action_group_invoked", "api_path": api_path}))

    params = {}
    try:
        props = event.get("requestBody", {}).get("content", {}).get("application/json", {}).get("properties", [])
        for p in props:
            params[p["name"]] = p["value"]
    except (KeyError, TypeError):
        pass

    if api_path == "/searchSimilarCases":
        try:
            result = search_similar_cases(params)
            body = json.dumps(result)
        except Exception as e:
            logger.error(f"Action group error: {e}")
            body = json.dumps({"cases": [], "total_found": 0, "error": str(e)})
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
