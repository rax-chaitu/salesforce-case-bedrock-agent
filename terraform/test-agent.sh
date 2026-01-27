#!/bin/bash
# Test script for Salesforce Agent (Bedrock Agent + API Gateway)
# Uses AWS IAM authentication via SigV4

set -e

cd "$(dirname "$0")"

# Configuration
AWS_PROFILE="${AWS_PROFILE:-SANDBOX5JAN27}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Get API URL from terraform output
API_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "")

if [ -z "$API_URL" ]; then
    echo "❌ Run 'terraform apply' first to deploy infrastructure"
    exit 1
fi

# Extract host from URL
API_HOST=$(echo "$API_URL" | sed 's|https://||' | sed 's|/.*||')

echo "🔗 API URL: $API_URL"
echo "🔑 AWS Profile: $AWS_PROFILE"
echo "🌎 Region: $AWS_REGION"
echo ""

# Test prompt (use argument or default)
TEST_PROMPT="${1:-What are common FinancialForce access issues?}"

# Health check (no auth needed typically, but try with auth)
echo "1️⃣  Health Check"
aws apigateway test-invoke-method \
  --rest-api-id "$(echo $API_HOST | cut -d'.' -f1)" \
  --resource-id "$(aws apigateway get-resources --rest-api-id "$(echo $API_HOST | cut -d'.' -f1)" --profile $AWS_PROFILE --region $AWS_REGION --query "items[?path=='/health'].id" --output text)" \
  --http-method GET \
  --profile $AWS_PROFILE \
  --region $AWS_REGION \
  --query 'body' --output text 2>/dev/null | python3 -m json.tool || echo "Health endpoint not available"
echo ""

# Agent invoke with IAM auth using awscurl
echo "2️⃣  Agent Invoke: \"$TEST_PROMPT\""
if command -v awscurl &> /dev/null; then
    awscurl --service execute-api \
      --region $AWS_REGION \
      --profile $AWS_PROFILE \
      -X POST "${API_URL}/agent/invoke" \
      -H "Content-Type: application/json" \
      -d "{\"prompt\": \"$TEST_PROMPT\"}" | python3 -m json.tool
else
    # Fallback: use AWS CLI to invoke Lambda directly
    echo "awscurl not installed, invoking Lambda directly..."
    LAMBDA_NAME=$(terraform output -raw lambda_function_name 2>/dev/null)
    aws lambda invoke \
      --function-name "$LAMBDA_NAME" \
      --profile $AWS_PROFILE \
      --region $AWS_REGION \
      --payload "$(echo -n '{"httpMethod":"POST","path":"/agent/invoke","body":"{\"prompt\":\"'"$TEST_PROMPT"'\"}"}' | base64)" \
      --cli-binary-format raw-in-base64-out \
      /tmp/lambda-response.json > /dev/null
    cat /tmp/lambda-response.json | python3 -m json.tool
fi
echo ""

# Case analyze
echo "3️⃣  Case Analysis"
if command -v awscurl &> /dev/null; then
    awscurl --service execute-api \
      --region $AWS_REGION \
      --profile $AWS_PROFILE \
      -X POST "${API_URL}/case/analyze" \
      -H "Content-Type: application/json" \
      -d '{
        "case_number": "00012345",
        "subject": "Need FF access",
        "description": "User needs FinancialForce access to log time entries",
        "priority": "Medium"
      }' | python3 -m json.tool
else
    echo "Skipped (awscurl not installed)"
fi
echo ""

# KB search
echo "4️⃣  Knowledge Base Search"
if command -v awscurl &> /dev/null; then
    awscurl --service execute-api \
      --region $AWS_REGION \
      --profile $AWS_PROFILE \
      -X POST "${API_URL}/kb/search" \
      -H "Content-Type: application/json" \
      -d '{"query": "password reset", "max_results": 3}' | python3 -m json.tool
else
    echo "Skipped (awscurl not installed)"
fi
echo ""

echo "✅ All tests completed"
echo ""
echo "💡 Tip: Install awscurl for full API testing: pip3 install awscurl"
