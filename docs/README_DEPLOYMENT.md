# AWS Bedrock AgentCore - Salesforce Integration Agent

> ⚠️ **ARCHIVED - NOT IN USE**
> 
> This documentation is for the **AgentCore approach** which was abandoned in favor of 
> simpler **Bedrock Agents**. Kept for historical reference only.
> 
> **Current Implementation**: See main [README.md](../README.md) for Bedrock Agent deployment.
> 
> **Why Abandoned**: AgentCore required Docker/ECR, 465+ lines of code, 8+ IAM policies, 
> and ~$15/month vs Bedrock Agent's ~$8/month with simpler setup.

---

This is a **production-ready AWS Bedrock AgentCore agent** with Salesforce integration capabilities, built using the Strands Agents framework. This template serves as a complete deployment guide for new AWS sandbox environments.

## 🚀 Quick Start for New AWS Sandbox

### Prerequisites
1. **AWS CLI** configured with appropriate permissions
2. **Docker Desktop** installed and running
3. **Terraform** >= 1.2
4. **Python 3.13+** with uv package manager
5. **AWS Bedrock Model Access** (Amazon Nova Pro recommended)

### Setup Steps

```bash
# 1. Clone/copy this project to new environment
# 2. Set AWS profile
export AWS_PROFILE=your-aws-profile-name

# 3. Start Docker (if not running)
open -a Docker

# 4. Navigate to project
cd salesforceagent

# 5. Deploy infrastructure
cd terraform
terraform init
terraform apply -auto-approve

# 6. Test the deployed agent
./test-agent.sh
```

## 📁 Project Structure

```
salesforceagent/
├── src/                    # Agent runtime code
│   ├── main.py            # AgentCore entrypoint
│   ├── salesforce_agent.py # Agent implementation
│   ├── knowledge_base.py  # Knowledge Base tools (RAG)
│   ├── model/load.py      # Model configuration
│   └── mcp_client/        # MCP client for tools
├── scripts/               # Utility scripts
│   └── export_sf_cases_to_kb.py  # SF case export for KB
├── mcp/                   # Model Context Protocol tools
│   └── lambda/            # Lambda-based MCP tools
├── terraform/             # Infrastructure as Code
│   ├── main.tf           # Main Terraform config
│   ├── bedrock_agentcore.tf # AgentCore resources + KB IAM
│   ├── api_gateway.tf    # API Gateway + Lambda
│   └── variables.tf      # Configuration variables
├── test/                  # Unit tests
├── lambda_function.py    # API Lambda handler (v3.1.0)
└── Dockerfile            # Container configuration
```

## 🛠 Detailed Setup Guide

### 1. Environment Configuration

```bash
# Configure AWS profile
aws configure --profile your-profile-name
export AWS_PROFILE=your-profile-name

# Verify access
aws sts get-caller-identity
```

### 2. Model Configuration

**⚠️ CRITICAL**: Update model configuration before deployment

Edit `src/model/load.py`:
```python
# Use Amazon Nova Pro (recommended for new sandboxes)
MODEL_ID = "amazon.nova-pro-v1:0"

# Alternative models (check regional availability):
# MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
# MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
```

### 3. Infrastructure Deployment

```bash
cd terraform

# Initialize Terraform
terraform init

# Review planned resources
terraform plan

# Deploy (creates 20+ AWS resources)
terraform apply -auto-approve
```

**Created Resources:**
- AgentCore Runtime & Endpoints (DEV/PROD)
- ECR Repository & Docker image
- Lambda functions for MCP tools
- Cognito authentication
- IAM roles & policies
- API Gateway (if needed)

### 4. Testing the Agent

**Method 1: AWS CLI (Recommended)**
```bash
# Generate test payload
echo '{"prompt": "Hello! Can you add 25 + 17 for me?"}' | base64 | tr -d '\n' > /tmp/payload_b64.txt

# Get runtime info
AGENT_RUNTIME_ID=$(terraform output -raw agentcore_runtime_id)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Invoke agent
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "arn:aws:bedrock-agentcore:us-east-1:${ACCOUNT_ID}:runtime/${AGENT_RUNTIME_ID}" \
  --qualifier "DEV" \
  --runtime-session-id "test-session-$(openssl rand -hex 16)" \
  --region us-east-1 \
  --payload "file:///tmp/payload_b64.txt" \
  /tmp/agent_response.json

# View clean response
grep '^data: ' /tmp/agent_response.json | sed 's/^data: "//' | sed 's/"$//' | tr -d '\n'
```

**Method 2: AgentCore CLI**
```bash
agentcore invoke '{"prompt": "what can you do?"}'
```

**Method 3: AWS Console**
- Navigate to Bedrock AgentCore Console
- Select your runtime
- Use "Test Console" with DEV qualifier
- Input: `{"prompt": "test message"}`

## 🔧 Troubleshooting Common Issues

### Docker Issues
```bash
# Problem: Docker daemon not running
# Solution:
open -a Docker
# Wait for Docker to start, then retry deployment
```

### Model Access Issues
```bash
# Problem: Claude models not available in region
# Solution: Switch to Amazon Nova Pro
# Edit src/model/load.py:
MODEL_ID = "amazon.nova-pro-v1:0"
```

### Terraform State Issues
```bash
# Clean state and redeploy
terraform destroy -auto-approve
rm -rf .terraform/
terraform init
terraform apply -auto-approve
```

### Base64 Payload Issues
```bash
# Ensure proper encoding for AWS CLI
echo '{"prompt": "your message"}' | base64 | tr -d '\n' > payload.txt
```

### AgentCore Runtime ARN Format
```bash
# Correct ARN format:
arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/RUNTIME_ID

# With endpoint qualifier:
arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID:runtime/RUNTIME_ID/runtime-endpoint/DEV
```

## 📋 Working Commands Reference

### Development Commands
```bash
# Local testing
cd src && python main.py

# Install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Run tests
pytest test/
```

### Deployment Commands
```bash
# Full deployment
cd terraform
terraform init
terraform apply -auto-approve

# Update only code
terraform apply -target=null_resource.docker_image

# View outputs
terraform output
```

### Monitoring Commands
```bash
# Check deployment status
terraform show

# View agent runtime logs
aws logs tail /aws/bedrock-agentcore/runtime/salesforceagent --follow

# Check ECR images
aws ecr describe-images --repository-name bedrock-agentcore/salesforceagent
```

## 🎯 Agent Capabilities

- **Math Operations**: Built-in add_numbers tool
- **Streaming Responses**: Real-time response delivery via Server-Sent Events (SSE)
- **MCP Integration**: Extensible tool framework
- **Salesforce Ready**: Framework for case analysis tools
- **Multi-Environment**: DEV/PROD endpoints

## 🔄 Template Usage for New Sandbox

1. **Copy project** to new environment
2. **Update variables.tf** with new settings
3. **Set AWS profile** for new sandbox
4. **Check model availability** in new region
5. **Run deployment** commands
6. **Test functionality** with provided scripts

## 📝 Configuration Files

### Key Files to Customize:
- `terraform/variables.tf` - Environment-specific settings
- `src/model/load.py` - Model configuration
- `terraform/terraform.tfvars` - Deployment variables
- `src/salesforce_agent.py` - Agent behavior

### Terraform Variables:
```hcl
app_name = "salesforceagent"
region = "us-east-1"
agent_runtime_version = "1.0"
```

## 🚨 Production Checklist

- [ ] **Security**: Secrets in AWS Secrets Manager
- [ ] **Monitoring**: CloudWatch observability enabled
- [ ] **CI/CD**: Automated deployment pipeline
- [ ] **Testing**: Comprehensive test coverage
- [ ] **Error Handling**: Graceful error responses
- [ ] **Access Control**: Proper IAM permissions
- [ ] **Documentation**: Updated integration guides

## 🎬 Lessons Learned from Issues

### Issue 1: Docker Daemon Not Running
**Problem**: Terraform fails with Docker command not found
**Solution**: Start Docker Desktop before deployment
```bash
open -a Docker
```

### Issue 2: Claude Model Access Denied
**Problem**: Anthropic Claude models not available in region/account
**Solution**: Switch to Amazon Nova Pro models
```python
MODEL_ID = "amazon.nova-pro-v1:0"
```

### Issue 3: Base64 Encoding for AWS CLI
**Problem**: Invalid base64 payload error
**Solution**: Proper base64 encoding without newlines
```bash
echo '{"prompt": "message"}' | base64 | tr -d '\n' > payload.txt
```

### Issue 4: Runtime Session ID Length
**Problem**: Session ID too short (minimum 33 characters)
**Solution**: Use proper UUID generation
```bash
openssl rand -hex 16  # Generates 32 character hex string
```

### Issue 5: AgentCore ARN Format
**Problem**: Incorrect ARN format causing validation errors
**Solution**: Use correct ARN structure:
```
arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/RUNTIME_ID
```

### Issue 6: Streaming Response Format
**Problem**: Response appears as `data: ...` chunks
**Explanation**: This is Server-Sent Events (SSE) format for real-time streaming
**Solution**: Use provided command to extract clean text:
```bash
grep '^data: ' response.json | sed 's/^data: "//' | sed 's/"$//' | tr -d '\n'
```

### Issue 7: Duplicate Terraform Resources
**Problem**: `terraform init` fails with "duplicate resource" errors
**Symptom**: `aws_lambda_function.agentcore_api_lambda` declared twice
**Root Cause**: Multiple .tf files defining same resources (api_only.tf and api_gateway.tf)
**Solution**: Remove or rename duplicate file:
```bash
mv terraform/api_only.tf terraform/api_only.tf.bak
terraform init
```

### Issue 8: Lambda AccessDeniedException on Agent Runtime
**Problem**: Lambda invokes wrong AgentCore runtime (different AWS account)
**Symptom**: `AccessDeniedException: User doesn't have permission to invoke this agent runtime`
**Root Cause**: Lambda environment variable `AGENT_RUNTIME_ARN` hardcoded to old account
**Solution**: Update Terraform to use dynamic ARN reference:
```hcl
# In api_gateway.tf - use Terraform reference instead of hardcoded value
environment {
  variables = {
    AGENT_RUNTIME_ARN = aws_bedrockagentcore_agent_runtime.agentcore_runtime.agent_runtime_arn
    # NOT: "arn:aws:bedrock-agentcore:us-east-1:OLD_ACCOUNT:runtime/old-id"
  }
}
```

### Issue 9: Lambda SSE Response Parsing - bytes vs dict
**Problem**: Lambda fails with `a bytes-like object is required, not 'str'`
**Root Cause**: boto3 1.40.4+ returns raw bytes from streaming response, not dict
**Symptom**: `event type: <class 'bytes'>` in CloudWatch logs
**Solution**: Handle raw bytes in invoke_agentcore():
```python
from io import BytesIO

def invoke_agentcore(prompt: str, session_id: str = None) -> str:
    payload_bytes = json.dumps({"prompt": prompt}).encode('utf-8')
    
    response = bedrock_agentcore.invoke_agent_runtime(
        agentRuntimeArn=os.environ['AGENT_RUNTIME_ARN'],
        qualifier=os.environ.get('AGENT_QUALIFIER', 'DEV'),
        runtimeSessionId=session_id,
        payload=BytesIO(payload_bytes)  # Use BytesIO, not dict
    )
    
    result = ""
    for event in response['response']:
        # Handle raw bytes (boto3 1.40.4+)
        if isinstance(event, bytes):
            chunk = event.decode('utf-8')
            for line in chunk.split('\n'):
                if line.strip().startswith('data: '):
                    data_content = line.strip()[6:].strip().strip('"')
                    if data_content:
                        result += data_content
    return result
```

### Issue 10: AWS Profile with Session Token
**Problem**: Temporary credentials expire, causing auth failures
**Solution**: Ensure AWS profile includes session token for sandbox access:
```bash
aws configure --profile sandbox-profile
# Enter: Access Key, Secret Key
# Also set session token:
aws configure set aws_session_token "YOUR_SESSION_TOKEN" --profile sandbox-profile
```

## 🔄 Complete New Sandbox Deployment Checklist

### Pre-Deployment Steps
```bash
# 1. Configure AWS Profile with new sandbox credentials
aws configure --profile new-sandbox
aws configure set aws_session_token "YOUR_TOKEN" --profile new-sandbox
export AWS_PROFILE=new-sandbox

# 2. Verify credentials
aws sts get-caller-identity

# 3. Start Docker Desktop
open -a Docker
# Wait 30 seconds for Docker daemon to be ready

# 4. Clean old Terraform state (if reusing project)
cd terraform
rm -rf .terraform terraform.tfstate*
```

### Deployment Steps
```bash
# 5. Initialize Terraform
terraform init

# 6. Update terraform.tfvars if needed
cat terraform.tfvars
# app_name = "salesforceagent"
# agent_runtime_version = "1"

# 7. Deploy all resources
terraform apply -auto-approve
# This creates ~36 resources: ECR, Cognito, Lambda, IAM, AgentCore, API Gateway

# 8. Note the outputs
terraform output
# agentcore_runtime_id = "salesforceagent_Agent-XXXX"
# api_gateway_invoke_url = "https://xxx.execute-api.region.amazonaws.com/prod"
# ecr_repository_url = "account.dkr.ecr.region.amazonaws.com/bedrock-agentcore/app"
```

### Post-Deployment Verification
```bash
# 9. Test health endpoint
API_URL=$(terraform output -raw api_gateway_invoke_url)
curl -X GET "${API_URL}/health"

# 10. Test agent invocation
curl -X POST "${API_URL}/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, what can you do?"}'

# 11. Test case analysis
curl -X POST "${API_URL}/case/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "case_number": "TEST-001",
    "subject": "Test Case",
    "description": "Testing deployment"
  }'

# 12. Test Knowledge Base search
curl -X POST "${API_URL}/kb/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "email integration", "maxResults": 5}'

# 13. Test Knowledge Base RAG
curl -X POST "${API_URL}/kb/rag" \
  -H "Content-Type: application/json" \
  -d '{"query": "How to resolve SMTP timeout errors?"}'
```

## 🧠 Knowledge Base Integration

This deployment includes Bedrock Knowledge Base integration for intelligent case resolution.

### Configuration
| Setting | Value |
|---------|-------|
| Knowledge Base ID | `<KB_ID>` |
| Data Source ID | `<DATASOURCE_ID>` |
| S3 Bucket | `testgenralbucketsf1` |
| Model | `amazon.nova-lite-v1:0` |

### Refresh KB Data from Salesforce
```bash
# Export cases from Salesforce CLI
python3 scripts/export_sf_cases_to_kb.py

# Upload to S3
aws s3 cp salesforce_cases_full.txt s3://testgenralbucketsf1/

# Sync Knowledge Base
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <KB_ID> \
  --data-source-id <DATASOURCE_ID> \
  --profile new-profile
```

## 📞 Support

For issues with this template:
1. Check troubleshooting section above
2. Verify AWS permissions and quotas
3. Ensure all prerequisites are installed
4. Review AWS CloudWatch logs for runtime errors

---

**Last Updated**: January 2025  
**AWS Bedrock AgentCore Version**: Latest  
**Terraform Version**: >= 1.2  
**boto3 Version**: 1.40.4+  
**Model**: Amazon Nova Pro v1.0  
**Features**: AgentCore + Knowledge Base RAG + Salesforce Integration