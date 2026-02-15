"""Reusable Salesforce query helpers. Requires rackspace_sf_auth layer for connection."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_sf():
    """Get SF connection from auth layer."""
    from rackspace_sf_auth import SalesforceAuthClient
    return SalesforceAuthClient().get_connection()


def query_sf(soql: str, sf=None) -> dict[str, Any]:
    """Execute a read-only SOQL query. Returns {records: [...], total_found: int}."""
    soql = soql.strip().rstrip(";")
    if not soql.upper().startswith("SELECT"):
        return {"error": "Only SELECT queries allowed", "records": [], "total_found": 0}
    if "LIMIT" not in soql.upper():
        soql += " LIMIT 10"

    sf = sf or _get_sf()
    results = sf.query(soql)
    records = results.get("records", [])
    for r in records:
        r.pop("attributes", None)
    return {"records": records, "total_found": results.get("totalSize", 0)}


def search_by_keywords(
    object_name: str,
    keyword_field: str,
    keywords: str,
    select_fields: list[str],
    filters: Optional[dict[str, str]] = None,
    max_results: int = 5,
    order_by: Optional[str] = None,
    sf=None,
) -> dict[str, Any]:
    """Search an object by keywords in a field with optional filters."""
    conditions = []
    for word in keywords.split()[:5]:
        safe = word.replace("'", "\\'")
        conditions.append(f"{keyword_field} LIKE '%{safe}%'")

    where = " OR ".join(conditions) if conditions else f"{keyword_field} != null"

    if filters:
        filter_clauses = []
        for k, v in filters.items():
            safe_v = v.replace("'", "\\'")
            filter_clauses.append(f"{k} = '{safe_v}'")
        where = f"({where}) AND {' AND '.join(filter_clauses)}"

    fields = ", ".join(select_fields)
    order = f" ORDER BY {order_by}" if order_by else ""
    soql = f"SELECT {fields} FROM {object_name} WHERE {where}{order} LIMIT {max_results}"

    return query_sf(soql, sf)


def get_record_by_id(
    object_name: str,
    record_id: str,
    fields: list[str],
    sf=None,
) -> dict[str, Any]:
    """Get a single record by ID."""
    safe_id = record_id.replace("'", "")
    fields_str = ", ".join(fields)
    soql = f"SELECT {fields_str} FROM {object_name} WHERE Id = '{safe_id}' LIMIT 1"
    result = query_sf(soql, sf)
    records = result.get("records", [])
    return {"record": records[0] if records else None, "found": len(records) > 0}


def get_related_records(
    parent_id: str,
    child_object: str,
    parent_field: str,
    fields: list[str],
    max_results: int = 5,
    order_by: Optional[str] = None,
    sf=None,
) -> dict[str, Any]:
    """Get child records related to a parent ID."""
    safe_id = parent_id.replace("'", "")
    fields_str = ", ".join(fields)
    order = f" ORDER BY {order_by}" if order_by else ""
    soql = f"SELECT {fields_str} FROM {child_object} WHERE {parent_field} = '{safe_id}'{order} LIMIT {max_results}"
    return query_sf(soql, sf)
