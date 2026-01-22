# AWS Bedrock AgentCore Salesforce Integration 🤖

A production-ready **Amazon Bedrock AgentCore** project for Salesforce case analysis with OAuth2 authentication, built with modern Infrastructure as Code (IaC) practices.

> **⚡ AgentCore vs Traditional Bedrock Agents**: This project uses the next-generation **AgentCore Runtime** platform (not traditional Bedrock Agents) for enterprise-grade agent deployment with built-in memory, observability, and governance.

## 📋 Project Overview

This project provides:
- 🔐 **Secure Salesforce Integration** using OAuth2 Connected Apps (no username/password)
- 🚀 **AgentCore Runtime Deployment** with direct code deployment (no Docker required)
- 📊 **Built-in Memory & Observability** for conversation tracking and monitoring
- 🏗️ **Infrastructure as Code** with both Terraform and CDK options
- 🔄 **Template-based Reusability** for AWS sandbox account cycles
- 🛡️ **Enterprise Security** with IAM roles and VPC networking support

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Bedrock AgentCore                        │
├─────────────────────────────────────────────────────────────────┤
│ AgentCore Runtime (Serverless)                                 │
│ ├─ Python Agent Code (Direct Deploy)                           │
│ ├─ Claude-3-Sonnet Foundation Model                            │
│ └─ Auto-scaling & Health Monitoring                            │
├─────────────────────────────────────────────────────────────────┤
│ Platform Services                                              │
│ ├─ Memory (STM/LTM conversation persistence)                   │
│ ├─ Identity (OAuth2 authentication)                            │
│ ├─ Gateway (API integrations via MCP)                          │
│ ├─ Observability (CloudWatch + OTEL traces)                    │
│ └─ Policy (Cedar-based governance)                             │
└─────────────────────────────────────────────────────────────────┘
            ↕ OAuth2 Flow
┌─────────────────────────────────────────────────────────────────┐
│                    Salesforce Org                              │
│ ├─ Connected App (Client ID/Secret)                            │
│ ├─ Case Management APIs                                        │
│ └─ Secure Token Exchange                                       │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- **AWS Account** with appropriate permissions
- **Python 3.10+** (verified compatible with 3.14)
- **AWS CLI** configured with profiles
- **Terraform** 1.2+ (installed via Homebrew)
- **Salesforce Connected App** configured with OAuth2

### Installation
```bash
# 1. Clone and setup
git clone <your-repo-url>
cd aws-bedrock-salesforce-agentcore
python3 -m venv venv
source venv/bin/activate

# 2. Install AgentCore toolkit
pip install bedrock-agentcore-starter-toolkit strands-agents

# 3. Verify installation
agentcore --help
```

### Environment Setup
```bash
# 1. Configure AWS credentials
aws configure --profile your-profile-name

# 2. Set up Salesforce credentials (create .env file)
cat > .env << EOF
SALESFORCE_CLIENT_ID=your_client_id_here
SALESFORCE_CLIENT_SECRET=your_client_secret_here
SALESFORCE_INSTANCE_URL=https://your-org.sandbox.salesforce.com
EOF
```

## 🛠️ Deployment Options

### Option 1: Production Template (Recommended)
```bash
# Create full production-ready project with IaC
agentcore create
# Choose:
# - Template: production
# - IaC: terraform
# - Model: anthropic.claude-3-sonnet
# - Framework: strands
```

### Option 2: Basic Runtime Template
```bash
# Create lightweight runtime-only project
agentcore create --template basic
```

### Option 3: Use Existing Terraform
```bash
# Deploy using existing Terraform configuration
cd terraform/
terraform init
terraform apply
```

## 🔧 Configuration

### Agent Configuration
```bash
# Configure for your environment
agentcore configure \
  --entrypoint agent.py \
  --region us-east-1 \
  --disable-memory \
  --execution-role arn:aws:iam::ACCOUNT:role/AgentCore-ExecutionRole
```

### Foundation Model Options
- `anthropic.claude-3-sonnet-20240229-v1:0` (Recommended)
- `anthropic.claude-3-haiku-20240307-v1:0` (Cost-effective)
- `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (Latest)

### Deployment Modes
```bash
# Cloud build (no Docker required) - DEFAULT
agentcore deploy

# Local development with hot reload
agentcore deploy --local

# Local build + cloud deployment
agentcore deploy --local-build
```

## 🧪 Testing

### Test Deployed Agent
```bash
# Basic test
agentcore invoke '{"prompt": "Hello! Test the Salesforce integration."}'

# With authentication
TOKEN=$(agentcore identity get-cognito-inbound-token)
agentcore invoke '{"prompt": "Analyze case #12345"}' --bearer-token "$TOKEN"

# Check status
agentcore status
```

### Test Scenarios
```bash
# 1. Case Analysis
agentcore invoke '{"prompt": "Analyze Salesforce case 001234567890 - customer login issues after password reset"}'

# 2. Priority Assessment  
agentcore invoke '{"prompt": "Review case priority for Enterprise customer John Smith, account issue"}'

# 3. Recommendations
agentcore invoke '{"prompt": "Suggest next steps for case: billing discrepancy, customer tier: Premium"}'
```

## 📁 Project Structure

### AgentCore Project Layout
```
aws-bedrock-salesforce-agentcore/
├── src/                          # Agent source code
│   ├── agent.py                  # Main agent handler
│   ├── salesforce_client.py      # OAuth2 Salesforce integration
│   └── requirements.txt          # Python dependencies
├── terraform/                    # Infrastructure as Code
│   ├── main.tf                   # AgentCore resources
│   ├── variables.tf               # Configuration variables
│   └── outputs.tf                # Deployment outputs
├── .bedrock_agentcore.yaml       # AgentCore configuration
├── .env.example                  # Environment template
└── README.md                     # This file
```

### Template Structure
```
TEMPLATE_FOR_NEW_ACCOUNTS/        # Reusable template
├── .bedrock_agentcore.yaml       # Pre-configured settings
├── terraform.tfvars.example      # AWS account template
├── deploy_terraform.sh           # Automated deployment
├── destroy_terraform.sh          # Cleanup script
└── NEW_ACCOUNT_CHECKLIST.md      # Setup guide
```

## 🔐 Security & Authentication

### Salesforce OAuth2 Setup
1. **Create Connected App** in Salesforce
2. **Configure OAuth Settings**:
   - Callback URL: `https://login.salesforce.com/services/oauth2/callback`
   - Scopes: `api`, `refresh_token`, `offline_access`
3. **Store credentials** in AWS Secrets Manager or AgentCore Identity

### AWS IAM Permissions
Required permissions for deployment:
- `bedrock-agentcore:*` (AgentCore runtime operations)
- `iam:CreateRole`, `iam:PassRole` (execution roles)
- `s3:*` (deployment artifacts)
- `codebuild:*` (container builds)
- `logs:*` (CloudWatch logging)

### Authentication Flows
- **Inbound**: Cognito JWT for agent access control
- **Outbound**: OAuth2 for Salesforce API calls
- **Service**: AWS IAM for platform services

## 🏗️ Infrastructure as Code

### Terraform Resources
The project deploys:
- **AgentCore Runtime** with auto-scaling
- **IAM Execution Role** with minimal permissions
- **Memory Resources** (optional STM/LTM)
- **Gateway Integration** (optional MCP)
- **VPC Configuration** (optional private networking)
- **CloudWatch Logging** with structured logs

### Terraform Commands
```bash
# Initialize
cd terraform && terraform init

# Plan deployment
terraform plan -var-file="terraform.tfvars"

# Deploy
terraform apply -auto-approve

# Destroy when done
terraform destroy -auto-approve
```

## 📊 Monitoring & Observability

### Built-in Observability
```bash
# Enable observability (one-time setup)
agentcore obs configure

# View agent traces
agentcore obs query --agent-id AGENT_ID --trace-type spans

# Monitor in AWS Console
# CloudWatch → GenAI Observability Dashboard
```

### Log Access
```bash
# Stream logs in real-time
aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ID-DEFAULT --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/AGENT_ID-DEFAULT \
  --filter-pattern "ERROR"
```

## 🔄 AWS Sandbox Account Lifecycle

### Template Workflow
When your AWS sandbox expires:

```bash
# 1. Clone template to new account
cp -r TEMPLATE_FOR_NEW_ACCOUNTS/ ../new-sandbox-deployment/
cd ../new-sandbox-deployment/

# 2. Update configuration
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with new account details

# 3. Deploy to new account
./deploy_terraform.sh

# 4. Test deployment
agentcore invoke '{"prompt": "Test new deployment"}'
```

### Checklist for New Accounts
- [ ] Configure AWS CLI profile
- [ ] Update `terraform.tfvars` with account ID
- [ ] Verify Salesforce Connected App access
- [ ] Enable required AWS services (Bedrock, AgentCore)
- [ ] Request foundation model access
- [ ] Deploy and test agent

## 🛠️ Development

### Local Development
```bash
# Start local dev server
agentcore dev

# Test locally (separate terminal)
agentcore invoke --dev '{"prompt": "Local test"}'

# Hot reload is automatic
```

### Adding Features
1. **Modify** `src/agent.py` with new functionality
2. **Test locally** with `agentcore dev`
3. **Deploy** with `agentcore deploy`
4. **Monitor** with `agentcore status`

### Debugging
```bash
# Check agent configuration
agentcore status --verbose

# View deployment details
terraform show

# Check permissions
aws sts get-caller-identity
```

## 📚 AgentCore Platform Services

### Memory (Optional)
```bash
# Enable memory for conversation persistence
agentcore configure --entrypoint agent.py
# Choose: STM (short-term) or STM+LTM (long-term)

# Memory commands
agentcore memory create my_agent_memory
agentcore memory status MEMORY_ID
```

### Gateway (Optional) 
```bash
# Create MCP gateway for API integrations
agentcore gateway create-mcp-gateway --name SalesforceGateway

# Add targets (APIs, Lambda functions)
agentcore gateway create-mcp-gateway-target \
  --gateway-arn GATEWAY_ARN \
  --target-type lambda
```

### Policy (Optional)
```bash
# Create policy engine for governance
agentcore policy create-policy-engine --name "CaseAnalysisPolicy"

# Generate policies from natural language
agentcore policy start-policy-generation \
  --content "Only allow case updates for assigned agents" \
  --resource-arn GATEWAY_ARN
```

## 🔧 Troubleshooting

### Common Issues
1. **Model Access Denied**
   ```bash
   # Request model access in Bedrock console
   # Use: anthropic.claude-3-sonnet-20240229-v1:0
   ```

2. **S3 Permission Errors**
   ```bash
   # AgentCore needs S3 bucket for deployments
   # Bucket created automatically: bedrock-agentcore-codebuild-sources-ACCOUNT-REGION
   ```

3. **Memory Not Found**
   ```bash
   # Disable memory if not needed
   agentcore configure --entrypoint agent.py --disable-memory
   ```

### Getting Help
```bash
# Check configuration
agentcore status --verbose

# View logs
aws logs tail /aws/bedrock-agentcore/runtimes/AGENT_ID-DEFAULT

# Test connectivity
agentcore invoke '{"prompt": "Health check"}'
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🔗 References

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AgentCore Starter Toolkit](https://aws.github.io/bedrock-agentcore-starter-toolkit/)
- [Strands Agents Framework](https://strandsagents.com/latest/)
- [Salesforce Connected Apps](https://help.salesforce.com/s/articleView?id=sf.connected_app_create.htm)

---

**Built with ❤️ using Amazon Bedrock AgentCore**