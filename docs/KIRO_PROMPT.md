# KIRO Initial Prompt - Salesforce Bedrock Agent

## Project Context
- **Location**: /Users/<USER>/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock
- **AWS Account**: sandbox4 (<AWS_ACCOUNT_ID>)
- **Status**: ✅ Successfully deployed on January 22, 2026

## Current Architecture
- **Standard Bedrock Agent** (NOT AgentCore) - simplified architecture
- Lambda handler: `lambda_function.py` (~150 lines)
- Terraform files in `terraform/` folder
- Knowledge Base ID: `<KB_ID>` (already exists)

## Deployed Resources
| Resource | Value |
|----------|-------|
| API Gateway URL | `https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod` |
| Bedrock Agent ID | `<AGENT_ID>` |
| DEV Alias ID | `<ALIAS_ID>` |
| PROD Alias ID | `<PROD_ALIAS_ID>` |
| Lambda Function | `salesforceagent-api` |

## API Endpoints
- `GET /health` - Health check
- `POST /agent/invoke` - Invoke Bedrock Agent with prompt
- `POST /case/analyze` - Analyze Salesforce case
- `POST /kb/search` - Direct KB vector search

## To Continue Development

### Before running Terraform:
```bash
eval "$(aws configure export-credentials --profile sandbox4 --format env)"
cd /Users/<USER>/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock/terraform
```

### Common Commands:
```bash
# Check status
terraform plan

# Apply changes
terraform apply

# Test endpoints
curl https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/health
```

## Potential Next Steps
1. Add authentication (API Key or Cognito)
2. Add request validation
3. Implement rate limiting
4. Add CloudWatch dashboards/alarms
5. Create Salesforce LWC component integration
6. Add streaming response support
7. Implement conversation memory

## Files to Modify
- `lambda_function.py` - API handler logic
- `terraform/bedrock_agent.tf` - Agent instructions/config
- `terraform/api_gateway.tf` - API Gateway settings
- `terraform/variables.tf` - Configuration variables

## Known Issues Resolved
See README.md "Deployment Log" section for detailed issues and solutions.
