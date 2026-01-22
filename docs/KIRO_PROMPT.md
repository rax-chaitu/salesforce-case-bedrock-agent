# KIRO Initial Prompt - Salesforce Bedrock Agent

## Project Context
- **Location**: /Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock
- **AWS Account**: sandbox4 (914296863611)
- **Status**: ✅ Successfully deployed on January 22, 2026

## Current Architecture
- **Standard Bedrock Agent** (NOT AgentCore) - simplified architecture
- Lambda handler: `lambda_function.py` (~150 lines)
- Terraform files in `terraform/` folder
- Knowledge Base ID: `TKYEX1S8ZP` (already exists)

## Deployed Resources
| Resource | Value |
|----------|-------|
| API Gateway URL | `https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod` |
| Bedrock Agent ID | `PVCXCBCV4I` |
| DEV Alias ID | `A7DTAVSVLJ` |
| PROD Alias ID | `RCRJ9TT1KX` |
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
cd /Users/venk7903/Documents/KIRO_Python_Projects/AWS_SANDBOX2_OnlyBedrock/terraform
```

### Common Commands:
```bash
# Check status
terraform plan

# Apply changes
terraform apply

# Test endpoints
curl https://9ed3wk8ehh.execute-api.us-east-1.amazonaws.com/prod/health
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
