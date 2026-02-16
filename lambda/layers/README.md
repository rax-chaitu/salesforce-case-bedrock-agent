# Reusable Lambda Layers & Shared Action Group

This directory contains reusable components shared across multiple Bedrock agents and Lambda functions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REUSABLE COMPONENTS                              │
└─────────────────────────────────────────────────────────────────────────┘

Lambda Layers (attached to any Lambda):
  ├── rackspace_sf_auth      → Salesforce JWT authentication
  └── rackspace_sf_queries   → SOQL query helpers

Shared Action Group (callable by any Bedrock agent):
  └── rackspace-sf-shared-action-group → Generic SOQL queries via /querySalesforce
```

---

## 1. rackspace_sf_auth Layer

**Purpose:** Salesforce JWT Bearer Token authentication  
**Location:** `lambda/layers/rackspace_sf_auth/`  
**Deployed ARN:** `arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-auth:1`

### Usage in Lambda

```python
from rackspace_sf_auth import SalesforceAuthClient

# Initialize (reads from env vars or Secrets Manager)
client = SalesforceAuthClient()

# Get simple-salesforce connection
sf = client.get_connection()

# Run SOQL query
result = sf.query("SELECT Id, Name FROM Account LIMIT 5")
for record in result['records']:
    print(record['Name'])

# Or get raw access token
token_data = client.get_access_token()
# Returns: {"access_token": "...", "instance_url": "https://rax--inttest.sandbox.my.salesforce.com"}
```

### Environment Variables

| Variable | Example | Description |
|----------|---------|-------------|
| `SALESFORCE_SECRET_NAME` | `salesforce-inttest-sandbox-jwt` | Secrets Manager secret name |
| `SALESFORCE_ENVIRONMENT` | `inttest` or `production` | Determines auth URL (test.salesforce.com vs login.salesforce.com) |

### Secret Format (Secrets Manager)

```json
{
  "client_id": "3MVG9...",
  "username": "integration-user@company.com.sandbox",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
}
```

**Naming Convention:**
- Sandbox/Inttest: `salesforce-inttest-sandbox-jwt`
- Production: `salesforce-production-jwt`

### Authentication Flow

```
1. Lambda reads SALESFORCE_SECRET_NAME env var
2. Fetch credentials from Secrets Manager (client_id, username, private_key)
3. Create JWT payload:
   {
     "iss": client_id,
     "sub": username,
     "aud": "https://test.salesforce.com" (or login.salesforce.com),
     "exp": current_time + 180 seconds
   }
4. Sign JWT with private_key using RS256 algorithm
5. POST to Salesforce OAuth endpoint:
   https://test.salesforce.com/services/oauth2/token
   grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
   assertion=<signed_jwt>
6. Receive access_token + instance_url
7. Create simple-salesforce connection
```

### Why JWT Bearer Token?

- ❌ **Client Credentials flow NOT supported** by Salesforce
- ✅ **JWT Bearer Token** is the standard for server-to-server auth
- ✅ No user interaction required
- ✅ Works with Connected App + X.509 certificate

### Dependencies Included

- `simple-salesforce` - Salesforce REST API client
- `PyJWT` - JWT encoding/decoding
- `cryptography` - RSA key handling
- `requests` - HTTP client

---

## 2. rackspace_sf_queries Layer

**Purpose:** Reusable SOQL query helpers  
**Location:** `lambda/layers/rackspace_sf_queries/`  
**Deployed ARN:** `arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-queries:1`

**Requires:** `rackspace_sf_auth` layer (for SF connection)

### Usage in Lambda

```python
from rackspace_sf_queries import query_sf, search_by_keywords

# Simple SOQL query
result = query_sf("SELECT Id, CaseNumber, Subject FROM Case WHERE Status='New' LIMIT 10")
print(f"Found {result['total_found']} cases")
for record in result['records']:
    print(f"{record['CaseNumber']}: {record['Subject']}")

# Keyword search with filters
result = search_by_keywords(
    object_name="Case",
    keyword_field="Subject",
    keywords="login password reset",
    select_fields=["Id", "CaseNumber", "Subject", "Status"],
    filters={"Status": "Closed", "Priority": "High"},
    max_results=10,
    order_by="ClosedDate DESC"
)
```

### Functions

#### `query_sf(soql: str) -> dict`

Execute a read-only SOQL query.

**Parameters:**
- `soql` (str): SOQL SELECT query

**Returns:**
```python
{
    "records": [{"Id": "...", "Name": "..."}, ...],
    "total_found": 42
}
```

**Safety:**
- Only SELECT queries allowed (no INSERT/UPDATE/DELETE)
- Auto-adds LIMIT 10 if not specified
- Strips `attributes` field from records

**Example:**
```python
result = query_sf("SELECT Id, Name FROM Account WHERE Industry='Technology'")
```

#### `search_by_keywords(...)` 

Search an object by keywords with filters.

**Parameters:**
- `object_name` (str): Salesforce object (e.g., "Case", "Account")
- `keyword_field` (str): Field to search (e.g., "Subject", "Name")
- `keywords` (str): Space-separated keywords
- `select_fields` (list): Fields to return
- `filters` (dict, optional): Field=Value filters
- `max_results` (int, default=5): Max records to return
- `order_by` (str, optional): ORDER BY clause

**Returns:** Same as `query_sf()`

**Example:**
```python
result = search_by_keywords(
    object_name="KnowledgeArticleVersion",
    keyword_field="Title",
    keywords="password reset login",
    select_fields=["Title", "UrlName", "Summary"],
    filters={"PublishStatus": "Online", "Language": "en_US"},
    max_results=5,
    order_by="LastModifiedDate DESC"
)
```

**Generated SOQL:**
```sql
SELECT Title, UrlName, Summary
FROM KnowledgeArticleVersion
WHERE (Title LIKE '%password%' OR Title LIKE '%reset%' OR Title LIKE '%login%')
  AND PublishStatus = 'Online'
  AND Language = 'en_US'
ORDER BY LastModifiedDate DESC
LIMIT 5
```

---

## 3. Shared Action Group

**Purpose:** Generic SOQL queries callable by any Bedrock agent  
**Location:** `lambda/shared_action_group/`  
**Lambda Name:** `rackspace-sf-shared-action-group`  
**API Gateway:** `https://vog41vh982.execute-api.us-east-1.amazonaws.com/prod`

### OpenAPI Schema

```json
{
  "openapi": "3.0.0",
  "paths": {
    "/querySalesforce": {
      "post": {
        "operationId": "querySalesforce",
        "summary": "Execute a read-only SOQL query",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "required": ["soql"],
                "properties": {
                  "soql": {
                    "type": "string",
                    "description": "SOQL SELECT query (e.g., 'SELECT Id, Name FROM Account LIMIT 5')"
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Usage in Bedrock Agent Instructions

```
If you need additional Salesforce data not available in your action groups, 
use the querySalesforce action to run a SOQL SELECT query.

Example: To get opportunity details:
querySalesforce(soql="SELECT Name, StageName, Amount FROM Opportunity WHERE Id = '006xxx'")
```

### Agent Call Example

**Agent invokes:**
```json
{
  "soql": "SELECT Name, StageName, Amount FROM Opportunity WHERE Id = '006Pe00000WvzKT'"
}
```

**Returns:**
```json
{
  "records": [
    {
      "Name": "Acme Corp - Cloud Migration",
      "StageName": "Closed Won",
      "Amount": 50000.0
    }
  ],
  "total_found": 1
}
```

### Safety Features

- ✅ Only SELECT queries allowed
- ✅ Auto-adds LIMIT 10 if missing
- ✅ Strips Salesforce `attributes` metadata
- ✅ Error handling with descriptive messages

---

## Deployment

### Deploy Layers

```bash
cd terraform
terraform apply -target=module.lambda_layer -target=module.sf_queries_layer
```

**Output:**
```
sf_auth_layer_arn = "arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-auth:1"
sf_queries_layer_arn = "arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-queries:1"
```

### Deploy Shared Action Group

```bash
terraform apply -target=module.shared_action_group
```

**Output:**
```
shared_action_group_function_name = "rackspace-sf-shared-action-group"
```

### Attach Layers to Lambda

**Terraform:**
```hcl
resource "aws_lambda_function" "my_function" {
  function_name = "my-sf-function"
  layers = [
    "arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-auth:1",
    "arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-queries:1"
  ]
  environment {
    variables = {
      SALESFORCE_SECRET_NAME    = "salesforce-inttest-sandbox-jwt"
      SALESFORCE_ENVIRONMENT    = "inttest"
    }
  }
}
```

**AWS CLI:**
```bash
aws lambda update-function-configuration \
  --function-name my-sf-function \
  --layers \
    arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-auth:1 \
    arn:aws:lambda:us-east-1:783330585869:layer:rackspace-sf-queries:1
```

---

## Testing

### Test Auth Layer

```python
# test_auth.py
from rackspace_sf_auth import SalesforceAuthClient

client = SalesforceAuthClient()
sf = client.get_connection()
result = sf.query("SELECT Id, Name FROM Account LIMIT 1")
print(f"Success! Found account: {result['records'][0]['Name']}")
```

### Test Queries Layer

```python
# test_queries.py
from rackspace_sf_queries import query_sf

result = query_sf("SELECT COUNT(Id) total FROM Case WHERE Status='New'")
print(f"New cases: {result['records'][0]['total']}")
```

### Test Shared Action Group

```bash
# Via API Gateway (requires IAM auth)
awscurl --service execute-api --region us-east-1 \
  -X POST "https://vog41vh982.execute-api.us-east-1.amazonaws.com/prod/querySalesforce" \
  -H "Content-Type: application/json" \
  -d '{"soql": "SELECT Id, CaseNumber FROM Case LIMIT 1"}'
```

---

## Future Agents Can Reuse

Any new Bedrock agent can:

1. **Attach layers** to their Lambda functions
2. **Call shared action group** for generic SOQL queries
3. **Create agent-specific action groups** for specialized logic

**Example: Opportunity Analysis Agent**

```python
# lambda/opportunity_agent/handler.py
from rackspace_sf_auth import SalesforceAuthClient
from rackspace_sf_queries import query_sf

def analyze_opportunity(opp_id):
    # Use shared layer for auth
    sf = SalesforceAuthClient().get_connection()
    
    # Use shared query helper
    result = query_sf(f"SELECT Name, Amount, StageName FROM Opportunity WHERE Id='{opp_id}'")
    
    # Agent-specific logic
    opp = result['records'][0]
    if opp['Amount'] > 100000:
        return "High-value opportunity - requires VP approval"
    return "Standard opportunity"
```

---

## Troubleshooting

### "No module named 'rackspace_sf_auth'"

**Cause:** Layer not attached to Lambda  
**Fix:** Add layer ARN to Lambda configuration

### "Unable to locate credentials"

**Cause:** `SALESFORCE_SECRET_NAME` env var not set  
**Fix:** Set environment variable in Lambda configuration

### "Salesforce login failed"

**Cause:** Invalid credentials in Secrets Manager  
**Fix:** Verify secret format and Connected App setup

### "Only SELECT queries allowed"

**Cause:** Tried to run INSERT/UPDATE/DELETE via `query_sf()`  
**Fix:** Use `sf.insert()`, `sf.update()` from simple-salesforce directly

---

## Layer Structure

```
lambda/layers/
├── rackspace_sf_auth/
│   ├── python/
│   │   ├── rackspace_sf_auth/
│   │   │   ├── __init__.py
│   │   │   └── auth.py          ← Main auth client
│   │   ├── simple_salesforce/   ← Dependency
│   │   ├── jwt/                 ← Dependency
│   │   └── cryptography/        ← Dependency
│   └── rackspace_sf_auth/       ← Symlink for local dev
│
└── rackspace_sf_queries/
    ├── python/
    │   └── rackspace_sf_queries/
    │       ├── __init__.py
    │       └── queries.py       ← Query helpers
    └── rackspace_sf_queries/    ← Symlink for local dev
```

**Why `python/` directory?**  
Lambda layers must have code in `python/` directory to be importable.

**Why symlink?**  
Allows local development without deploying layer every time.

---

## Best Practices

1. **Version layers** - Increment version when making breaking changes
2. **Test locally** - Use symlinks to test without deploying
3. **Document changes** - Update this README when adding functions
4. **Keep layers small** - Only include necessary dependencies
5. **Reuse across projects** - These layers work for any SF integration

---

## Related Documentation

- [Salesforce JWT Auth Setup](../../docs/SALESFORCE_AUTH_IMPLEMENTATION.md)
- [Connected App Configuration](../../docs/SALESFORCE_CONNECTED_APP_GUIDE.md)
- [Technical Flow](../../docs/TECHNICAL_FLOW.md)
