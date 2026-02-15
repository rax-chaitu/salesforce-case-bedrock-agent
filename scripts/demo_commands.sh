#!/bin/bash
# ============================================================
# SF Case Analysis Agent - Demo Commands
# ============================================================
# Prerequisites:
#   aws sso login --profile SANDBOX9FEB9
#   export AWS_PROFILE=SANDBOX9FEB9
# ============================================================

API_URL="https://i929iwo1t6.execute-api.us-east-1.amazonaws.com/prod"

# --- Health Check ---
echo "=== Health Check ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  "$API_URL/health"

echo -e "\n\n"

# --- Scenario 1: Opportunity Team Member Request (Self-Service) ---
echo "=== Scenario 1: Opportunity Team Member Request ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  -X POST "$API_URL/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00151296",
    "subject": "Need to be Added as Client Partner",
    "description": "Please add me as Client Partner for this opp",
    "priority": "High",
    "status": "New",
    "tool": "Salesforce",
    "support_reason": "Opportunity - Add/Change Team Member or Split"
  }'

echo -e "\n\n"

# --- Scenario 2: Account Ownership Transfer (GAR Tool) ---
echo "=== Scenario 2: Account Ownership Transfer ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  -X POST "$API_URL/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00151301",
    "subject": "Transfer account ownership from John Smith to Jane Doe",
    "description": "John Smith has moved to a different team. Need to reassign his accounts to Jane Doe who is taking over the territory.",
    "priority": "High",
    "status": "New",
    "tool": "Salesforce",
    "support_reason": "Account - Ownership Change"
  }'

echo -e "\n\n"

# --- Scenario 3: New User Access ---
echo "=== Scenario 3: New User Access ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  -X POST "$API_URL/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00151302",
    "subject": "New user needs Salesforce access",
    "description": "New hire Sarah Johnson starting Monday needs Salesforce access with Sales Rep profile and ZoomInfo license.",
    "priority": "High",
    "status": "New",
    "tool": "Salesforce",
    "support_reason": "User Access - New User Setup"
  }'

echo -e "\n\n"

# --- Scenario 4: Company Access Request (Self-Service) ---
echo "=== Scenario 4: Company Access Request ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  -X POST "$API_URL/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00151303",
    "subject": "Need access to Company - Acme Corp",
    "description": "I need to create opportunities under Acme Corp but I dont have access to the company. Please grant me access.",
    "priority": "Medium",
    "status": "New",
    "tool": "Salesforce",
    "support_reason": "Company - Access Request"
  }'

echo -e "\n\n"

# --- Scenario 5: Opportunity Amount Change ---
echo "=== Scenario 5: Opportunity Amount Change ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  -X POST "$API_URL/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00151300",
    "subject": "Need to change Opportunity Amount to 150000",
    "description": "The opportunity amount needs to be updated from 100000 to 150000 due to contract amendment.",
    "priority": "Medium",
    "status": "New",
    "tool": "Salesforce",
    "support_reason": "Opportunity - Amount Change"
  }'

echo -e "\n\n"

# --- Direct KB Search (shows what the agent retrieves) ---
echo "=== Direct KB Search: GAR Tool ==="
awscurl --service execute-api --region us-east-1 --profile SANDBOX9FEB9 \
  -X POST "$API_URL/kb/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to transfer account ownership using GAR tool",
    "max_results": 3
  }'
