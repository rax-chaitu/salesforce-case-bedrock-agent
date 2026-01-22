#!/bin/bash
# Test script for Salesforce Agent (Bedrock Agent + API Gateway)

set -e

cd "$(dirname "$0")"

# Get API URL from terraform output
API_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo "❌ Run 'terraform apply' first to deploy infrastructure"
    exit 1
fi

echo "🔗 API URL: $API_URL"
echo ""

# Health check
echo "1️⃣  Health Check"
curl -s "${API_URL}/health" | python3 -m json.tool
echo ""

# Agent invoke
echo "2️⃣  Agent Invoke"
curl -s -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are common FinancialForce access issues?"}' | python3 -m json.tool
echo ""

# Case analyze
echo "3️⃣  Case Analysis"
curl -s -X POST "${API_URL}/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "00012345",
    "subject": "Need FF access",
    "description": "User needs FinancialForce access to log time entries",
    "priority": "Medium"
  }' | python3 -m json.tool
echo ""

# KB search
echo "4️⃣  Knowledge Base Search"
curl -s -X POST "${API_URL}/kb/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "password reset", "max_results": 3}' | python3 -m json.tool
echo ""

echo "✅ All tests completed"
