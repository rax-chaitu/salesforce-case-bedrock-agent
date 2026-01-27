# Terraform Basics for Salesforce Developers

A quick guide to Terraform concepts mapped to Salesforce equivalents.

---

## What is Terraform?

**Terraform = "Metadata Deployment for AWS"**

Think of it like Change Sets or SFDX but for AWS infrastructure.

| Salesforce Concept | Terraform Equivalent |
|-------------------|---------------------|
| Metadata XML files | `.tf` files |
| `sf project deploy start` | `terraform apply` |
| `sf project deploy preview` | `terraform plan` |
| Sandbox refresh | `terraform destroy` + `terraform apply` |
| Package.xml | `main.tf` (defines what to create) |
| Custom Settings / Named Credentials | `terraform.tfvars` (config values) |
| Unlocked Packages | `modules/` (reusable components) |

---

## Project Structure

```
terraform/
├── main.tf              # Orchestrates everything (like Package.xml)
├── variables.tf         # Input parameters (like Custom Metadata Type)
├── terraform.tfvars     # YOUR values (like Custom Settings records) - NEVER COMMIT!
├── terraform.tfvars.example  # Template for tfvars
├── api_gateway.tf       # REST API definition
├── locals.tf            # Computed values
├── terraform.tfstate    # Tracks deployed resources - DON'T DELETE!
└── modules/             # Reusable components
    ├── bedrock_agent/   # AI Agent setup
    ├── lambda/          # Python function (like Apex trigger)
    ├── sqs/             # Message queue (like Platform Events)
    ├── eventbridge/     # Event routing (like Process Builder)
    └── secrets/         # Credentials (like Named Credentials)
```

---

## Key Files Explained

### `variables.tf` - Defines WHAT inputs are needed
```hcl
variable "salesforce_instance_url" {
  description = "Your Salesforce org URL"
  type        = string
  default     = ""  # Optional default value
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}
```
*Like Custom Metadata Type definition - defines structure, not values.*

### `terraform.tfvars` - YOUR actual values
```hcl
salesforce_instance_url = "https://rackspace--sandbox.sandbox.my.salesforce.com"
salesforce_client_id    = "3MVG9..."
knowledge_base_id       = "TKYEX1S8ZP"
```
*Like Custom Settings records - your org-specific values. NEVER commit to git!*

### `main.tf` - Wires everything together
```hcl
# Call a module (like referencing an Unlocked Package)
module "lambda" {
  source = "./modules/lambda"
  
  # Pass variables to module
  salesforce_instance_url = var.salesforce_instance_url
  bedrock_agent_id        = module.bedrock_agent.agent_id
}

# Use module outputs
output "lambda_function_name" {
  value = module.lambda.function_name
}
```

### `terraform.tfstate` - Tracks what's deployed
- Terraform compares: state file vs AWS vs your `.tf` files
- Determines what to create/update/delete
- **Never edit manually!**
- **Never delete!** (or Terraform loses track of resources)

---

## Essential Commands

| Command | What it does | Salesforce Equivalent |
|---------|--------------|----------------------|
| `terraform init` | Download providers, initialize | Install SFDX plugins |
| `terraform plan` | Preview changes (safe, read-only) | `sf project deploy preview` |
| `terraform apply` | Deploy changes | `sf project deploy start` |
| `terraform destroy` | Delete all resources | Delete sandbox |
| `terraform output` | Show deployed values | View deployment results |
| `terraform validate` | Check syntax | Validate metadata |
| `terraform fmt` | Auto-format code | Prettier for TF |

---

## Typical Workflow

```bash
# 1. First time only - initialize
terraform init

# 2. Preview what will change (ALWAYS do this first!)
terraform plan

# 3. If plan looks good, apply
terraform apply

# 4. View outputs (API URLs, IDs, etc.)
terraform output
```

---

## Common Patterns

### Reading a variable
```hcl
# In variables.tf
variable "project_name" {
  type    = string
  default = "salesforceagent"
}

# Using it anywhere
name = var.project_name
name = "${var.project_name}-lambda"  # String interpolation
```

### Using module outputs
```hcl
# Module outputs a value
# modules/sqs/main.tf
output "queue_arn" {
  value = aws_sqs_queue.main.arn
}

# Parent uses it
# main.tf
module "lambda" {
  sqs_queue_arn = module.sqs.queue_arn
}
```

### Conditional resources
```hcl
# Create only if variable is set
resource "aws_secretsmanager_secret_version" "key" {
  count     = var.private_key != "" ? 1 : 0  # 1 = create, 0 = skip
  secret_id = aws_secretsmanager_secret.key.id
}
```

### Tags (like Salesforce record metadata)
```hcl
tags = {
  Project   = var.project_name
  ManagedBy = "Terraform"
  Environment = "production"
}
```

---

## AWS Credentials Setup

```bash
# Option 1: SSO Login (recommended)
aws sso login --profile sandbox4
eval $(aws configure export-credentials --profile sandbox4 --format env)

# Option 2: Export profile
export AWS_PROFILE=sandbox4

# Verify credentials
aws sts get-caller-identity
```

---

## Troubleshooting

### "No valid credential sources found"
```bash
# SSO token expired - re-login
aws sso login --profile YOUR_PROFILE
```

### "Resource already exists"
```bash
# Import existing resource into state
terraform import aws_sqs_queue.main https://sqs.us-east-1.amazonaws.com/ACCOUNT/queue-name
```

### "State file locked"
```bash
# Force unlock (use carefully!)
terraform force-unlock LOCK_ID
```

### Want to start fresh?
```bash
# Destroy all resources
terraform destroy

# Remove state (CAUTION: loses track of resources!)
rm terraform.tfstate terraform.tfstate.backup

# Re-initialize
terraform init
```

---

## Key Gotchas

1. **State file** - Don't delete `terraform.tfstate`! It tracks what's deployed
2. **tfvars** - Never commit to git (has secrets)
3. **Plan first** - Always run `terraform plan` before `apply`
4. **Idempotent** - Running `apply` twice won't duplicate resources
5. **Dependencies** - Terraform figures out order automatically
6. **Destroy is permanent** - No recycle bin!

---

## Quick Reference Card

```bash
# Initialize (first time)
terraform init

# Preview changes
terraform plan

# Deploy
terraform apply

# Deploy without confirmation prompt
terraform apply -auto-approve

# Show current outputs
terraform output

# Show specific output
terraform output api_gateway_url

# Destroy everything
terraform destroy

# Format all .tf files
terraform fmt -recursive

# Validate syntax
terraform validate
```

---

## Resources

- [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Terraform Language Docs](https://developer.hashicorp.com/terraform/language)
- [AWS Bedrock Terraform Resources](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/bedrockagent_agent)
