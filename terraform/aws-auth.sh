#!/bin/bash
# AWS Authentication Helper
# Run: source aws-auth.sh

PROFILE="${AWS_PROFILE:-SANDBOX5JAN27}"

echo "🔐 Authenticating with AWS profile: $PROFILE"

# Check if SSO login needed
if ! aws sts get-caller-identity --profile "$PROFILE" &>/dev/null; then
    echo "⏳ SSO token expired, logging in..."
    aws sso login --profile "$PROFILE"
fi

# Export credentials to environment
eval $(aws configure export-credentials --profile "$PROFILE" --format env)

# Verify
if aws sts get-caller-identity &>/dev/null; then
    echo "✅ Authenticated successfully"
    aws sts get-caller-identity --query 'Account' --output text | xargs -I {} echo "   Account: {}"
else
    echo "❌ Authentication failed"
    exit 1
fi
