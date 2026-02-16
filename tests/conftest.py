"""
conftest.py - Shared fixtures and mocks for all tests.
Patches external dependencies (Salesforce, Bedrock) so tests run locally.

Run all: python3 -m pytest tests/ -v
"""

import sys
import os
import json
import importlib
import pytest
from unittest.mock import MagicMock

# =============================================================================
# MOCK EXTERNAL DEPENDENCIES (before any Lambda imports)
# =============================================================================

# Mock rackspace_sf_auth layer
mock_sf_auth_module = MagicMock()
mock_sf_auth_client = MagicMock()
mock_sf_auth_client.is_configured.return_value = True
mock_sf_auth_client.check_connection.return_value = {"connected": True, "instance_url": "https://test.salesforce.com"}
mock_sf_auth_module.SalesforceAuthClient.return_value = mock_sf_auth_client
sys.modules["rackspace_sf_auth"] = mock_sf_auth_module

# Mock simple_salesforce
sys.modules["simple_salesforce"] = MagicMock()

# Mock boto3 for bedrock_client
mock_boto3 = MagicMock()
sys.modules.setdefault("boto3", mock_boto3)
sys.modules.setdefault("botocore", MagicMock())
sys.modules.setdefault("botocore.exceptions", MagicMock())

# Set env vars
os.environ.setdefault("BEDROCK_AGENT_ID", "test-agent-id")
os.environ.setdefault("BEDROCK_AGENT_ALIAS_ID", "test-alias-id")
os.environ.setdefault("BEDROCK_KNOWLEDGE_BASE_ID", "test-kb-id")

# =============================================================================
# MODULE LOADERS (handle name collision between handler.py files)
# =============================================================================

CASE_PROCESSOR_PATH = os.path.join(os.path.dirname(__file__), "..", "lambda", "case_processor")
ACTION_GROUP_PATH = os.path.join(os.path.dirname(__file__), "..", "lambda", "action_group")


@pytest.fixture(scope="session")
def case_handler():
    """Import case_processor/handler.py as a module."""
    sys.path.insert(0, CASE_PROCESSOR_PATH)
    # Force reimport to get case_processor's handler
    if "handler" in sys.modules:
        del sys.modules["handler"]
    if "bedrock_client" in sys.modules:
        del sys.modules["bedrock_client"]
    if "salesforce_client" in sys.modules:
        del sys.modules["salesforce_client"]
    import handler
    return handler


@pytest.fixture(scope="session")
def sf_client_module():
    """Import case_processor/salesforce_client.py."""
    sys.path.insert(0, CASE_PROCESSOR_PATH)
    if "salesforce_client" in sys.modules:
        del sys.modules["salesforce_client"]
    import salesforce_client
    return salesforce_client


@pytest.fixture(scope="session")
def action_handler():
    """Import action_group/handler.py as a module."""
    # Remove case_processor handler first
    for mod in ["handler", "bedrock_client", "salesforce_client"]:
        sys.modules.pop(mod, None)
    sys.path.insert(0, ACTION_GROUP_PATH)
    import handler
    return handler


# =============================================================================
# SHARED FIXTURES
# =============================================================================

@pytest.fixture
def mock_sf_connection():
    """Mock Salesforce connection."""
    sf = MagicMock()
    sf.sf_instance = "rax--inttest.sandbox.my.salesforce.com"
    sf.query.return_value = {"records": [], "totalSize": 0}
    return sf


@pytest.fixture
def sample_case_data():
    return {
        "Subject": "Test Similar Cases Format - Opportunity Amount",
        "Description": "Please update opportunity amount to 90000",
        "Support_Reason__c": "Opportunity - Amount Change",
        "Tool__c": "Salesforce",
        "Priority": "Medium",
        "Case_Number__c": "00145633",
    }


@pytest.fixture
def sample_agent_response():
    return json.dumps({
        "summary": "Request to update opportunity amount to 90000.",
        "category": "Opportunity",
        "severity": "Medium",
        "root_cause": "User needs to update the opportunity amount.",
        "admin_steps": ["1. Navigate to Opportunity", "2. Check Record Type", "3. Update amount"],
        "user_steps": ["1. Navigate to Opportunity", "2. Click Request Amount Change"],
        "similar_cases": ["00131235", "00117967", "00128040"],
        "kb_articles": ["Amount - Opportunities SOP", "Optimizer+ Amount Guidelines"],
        "estimated_resolution": "15 minutes",
        "recommendation": "Check Record Type first.",
        "self_resolvable": True,
        "ai_disclaimer": "AI-generated.",
    })


@pytest.fixture
def sample_agent_response_no_user_steps():
    return json.dumps({
        "summary": "Complex data migration.", "category": "Data_Update", "severity": "High",
        "root_cause": "Bulk update.", "admin_steps": ["1. Export", "2. Transform", "3. Import"],
        "user_steps": [], "similar_cases": ["00140001"], "kb_articles": [],
        "estimated_resolution": "2 hours", "recommendation": "Admin only.",
        "self_resolvable": False, "ai_disclaimer": "AI.",
    })


@pytest.fixture
def sample_agent_response_circular_steps():
    return json.dumps({
        "summary": "Tool access request.", "category": "User_Access", "severity": "Low",
        "root_cause": "Needs Outreach.", "admin_steps": ["1. Grant access"],
        "user_steps": ["1. Navigate to request page", "2. Fill form", "3. Submit the case to admin"],
        "similar_cases": [], "kb_articles": ["Outreach Access SOP"],
        "estimated_resolution": "30 min", "recommendation": "Grant access.",
        "self_resolvable": True, "ai_disclaimer": "AI.",
    })


@pytest.fixture
def sample_kav_results():
    return {
        "records": [
            {"Title": "Sales Managers \u2013 How to modify an opportunity\u2019s amount when it has a quote?",
             "UrlName": "Sales-Managers-How-to-modify-an-opportunity-s-amount-when-it-has-a-quote"},
            {"Title": "Create a Salesforce Case", "UrlName": "Create-a-Salesforce-Case"},
            {"Title": "ProServ Opportunity Fees Calculating Incorrectly", "UrlName": "ProServ-Opportunity-Fees"},
        ],
        "totalSize": 3,
    }


@pytest.fixture
def sample_similar_cases_records():
    return {
        "records": [
            {"Id": "500Pe00000Case01", "CaseNumber": "00131235", "Subject": "Update amount",
             "Support_Reason__c": "Opportunity - Amount Change", "Description": "Update",
             "Case_Closure_Notes__c": "Done via QM", "ClosedDate": "2024-06-15T10:00:00.000+0000",
             "Close_Codes__c": "Resolved", "Close_Reason__c": "Completed",
             "Root_Cause_of_Inquiry__c": "Amount", "Tool__c": "Salesforce",
             "Department__c": "Sales", "Segment__c": "Enterprise",
             "DP_Resolution__c": "Updated", "Admin_Notes__c": "Done",
             "CaseComments": {"records": [{"CommentBody": "Updated"}, {"CommentBody": "Verified"}]},
             "EmailMessages": {"records": [{"Subject": "Re: Amount", "TextBody": "Please update"}]}},
            {"Id": "500Pe00000Case02", "CaseNumber": "00117967", "Subject": "Change amount",
             "Support_Reason__c": "Opportunity - Amount Change", "Description": "Need update",
             "Case_Closure_Notes__c": None, "ClosedDate": "2025-01-10T10:00:00.000+0000",
             "Close_Codes__c": None, "Close_Reason__c": None, "Root_Cause_of_Inquiry__c": None,
             "Tool__c": "Salesforce", "Department__c": None, "Segment__c": None,
             "DP_Resolution__c": None, "Admin_Notes__c": None,
             "CaseComments": None, "EmailMessages": None},
        ],
        "totalSize": 2,
    }
