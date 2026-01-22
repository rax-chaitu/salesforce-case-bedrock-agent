# Salesforce AgentCore Integration with PKCE OAuth

This project integrates Salesforce with AWS Bedrock AgentCore using PKCE (Proof Key for Code Exchange) OAuth flow for enhanced security.

## Overview

The integration provides:
- **Secure PKCE OAuth flow** for Salesforce authentication
- **REST API endpoints** for case analysis and escalation checks
- **AWS Bedrock AgentCore** integration for AI-powered case analysis
- **FastAPI web interface** for easy testing and integration

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Salesforce    │    │   FastAPI App   │    │  AWS Bedrock    │
│   Connected App │◄──►│   (PKCE Flow)   │◄──►│   AgentCore     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
   OAuth PKCE Flow         REST API Wrapper       AI Case Analysis
```

## Prerequisites

### 1. Salesforce Connected App Configuration

Create a Connected App in Salesforce with PKCE support:

1. **Setup → App Manager → New Connected App**
2. **Basic Information:**
   - Connected App Name: `AgentCore PKCE Integration`
   - API Name: `AgentCore_PKCE`
   - Contact Email: Your email

3. **API (Enable OAuth Settings):**
   - ✅ Enable OAuth Settings
   - **Callback URL:** `http://localhost:8000/oauth/callback`
   - **Selected OAuth Scopes:**
     - Access and manage your data (api)
     - Perform requests on your behalf at any time (refresh_token)
     - Access your basic information (id)

4. **Advanced Settings:**
   - ✅ **Enable PKCE Extension for Supported Authorization Flows**
   - ✅ **Require Proof Key for Code Exchange (PKCE) Extension**
   - ❌ Client Credentials Flow (disable for PKCE)

5. **Save and Note:**
   - **Consumer Key** (Client ID)
   - **Consumer Secret** (not needed for PKCE, but can be stored)

### 2. AWS Environment Setup

1. **AWS Bedrock AgentCore deployed** (see main README)
2. **AWS CLI configured** with proper permissions
3. **Environment variables configured**

### 3. Environment Configuration

Create `.env` file:

```bash
# Salesforce PKCE Configuration
SF_CLIENT_ID=3MVG9XhRuzJUtKtDuUFI7ZxAn0lxqsw0ebcAc7cOqnOHZzsnU37o7qCJnMPkPPQ1Gw_t0ms0AC53eQWrmDIcD
SF_INSTANCE_URL=https://rax--inttest.sandbox.my.salesforce.com
SF_REDIRECT_URI=http://localhost:8000/oauth/callback

# AWS AgentCore Configuration
AWS_REGION=us-east-1
AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:636750015252:runtime/salesforceagent_Agent-7VTeMP8Ti7
AGENT_QUALIFIER=DEV
```

## Installation and Setup

### 1. Install Dependencies

```bash
cd api/
pip install -r requirements.txt
```

### 2. Start the PKCE API Server

```bash
# Using the PKCE-enabled FastAPI app
python app_pkce.py
```

The server will start at `http://localhost:8000`

## PKCE OAuth Flow

### Step 1: Initiate OAuth Flow

**GET** `/oauth/authorize`

```bash
curl -X GET "http://localhost:8000/oauth/authorize"
```

**Response:**
```json
{
  "authorization_url": "https://rax--inttest.sandbox.my.salesforce.com/services/oauth2/authorize?response_type=code&client_id=3MVG9...&redirect_uri=http%3A//localhost%3A8000/oauth/callback&code_challenge=xyz...&code_challenge_method=S256&scope=api+refresh_token+full&state=abc...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "instructions": [
    "1. Visit the authorization_url in your browser",
    "2. Log in to Salesforce and authorize the application",
    "3. You will be redirected back to /oauth/callback",
    "4. Use the returned access_token for API calls"
  ]
}
```

### Step 2: User Authorization

1. **Visit the `authorization_url`** in your browser
2. **Log in to Salesforce** with your credentials
3. **Authorize the application** when prompted
4. **Automatic redirect** to callback URL with access token

### Step 3: Use Access Token

After successful OAuth, you'll get an access token to use with API endpoints.

## API Endpoints

### 1. List Salesforce Cases

**GET** `/salesforce/cases`

```bash
curl -X GET "http://localhost:8000/salesforce/cases?access_token=YOUR_ACCESS_TOKEN&limit=5&status=New"
```

### 2. Analyze Case with AgentCore

**POST** `/salesforce/analyze-case`

```bash
curl -X POST "http://localhost:8000/salesforce/analyze-case" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "5004U000012A3bSQAS",
    "access_token": "YOUR_ACCESS_TOKEN"
  }'
```

### 3. Check Case Escalation

**POST** `/salesforce/escalation-check`

```bash
curl -X POST "http://localhost:8000/salesforce/escalation-check" \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "5004U000012A3bSQAS",
    "access_token": "YOUR_ACCESS_TOKEN"
  }'
```

### 4. Direct Agent Invocation

**POST** `/agent/invoke`

```bash
curl -X POST "http://localhost:8000/agent/invoke" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze this customer support case and provide recommendations"
  }'
```

## Security Features

### PKCE (Proof Key for Code Exchange)

- **Code Verifier:** Random 43-128 character string
- **Code Challenge:** SHA256 hash of code verifier, base64url encoded
- **State Parameter:** CSRF protection
- **No Client Secret:** Enhanced security for public clients

### Benefits of PKCE vs Client Credentials:

1. **No Client Secret Required:** Eliminates secret exposure risk
2. **CSRF Protection:** State parameter prevents cross-site request forgery
3. **Authorization Code Flow:** User explicitly authorizes access
4. **Refresh Tokens:** Long-lived access without re-authorization
5. **Salesforce Best Practice:** Recommended by Salesforce for modern apps

## Testing

### 1. Test PKCE Flow

```bash
# Start the server
python api/app_pkce.py

# Open browser and visit
open "http://localhost:8000/oauth/authorize"
```

### 2. Test AgentCore Integration

```bash
# Test with sample case data
python test_agentcore_analysis.py
```

### 3. Integration Testing

```bash
# Create a test script
cat > test_pkce_integration.py << 'EOF'
#!/usr/bin/env python3
import requests

# Test OAuth initiation
response = requests.get('http://localhost:8000/oauth/authorize')
print("OAuth Init:", response.json())

# Test direct agent invocation (no OAuth needed)
response = requests.post(
    'http://localhost:8000/agent/invoke',
    json={'prompt': 'Hello, can you help analyze a support case?'}
)
print("Agent Response:", response.json())
EOF

python test_pkce_integration.py
```

## Deployment

### Production Considerations

1. **HTTPS Required:** OAuth flows must use HTTPS in production
2. **Session Storage:** Use Redis or database instead of in-memory storage
3. **Error Handling:** Implement comprehensive error handling and logging
4. **Rate Limiting:** Add rate limiting for API endpoints
5. **Token Refresh:** Implement automatic token refresh logic

### Environment Variables for Production

```bash
# Production Salesforce
SF_CLIENT_ID=your_production_client_id
SF_INSTANCE_URL=https://yourorg.my.salesforce.com
SF_REDIRECT_URI=https://yourdomain.com/oauth/callback

# Production AWS
AWS_REGION=us-east-1
AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:account:runtime/prod_agent
AGENT_QUALIFIER=PROD
```

## Troubleshooting

### Common Issues

1. **"Enable PKCE Extension" not available**
   - Ensure you're creating a new Connected App
   - Check Salesforce edition supports PKCE
   - Contact Salesforce admin for permissions

2. **OAuth callback not working**
   - Verify redirect URI matches exactly in Connected App
   - Check firewall/proxy settings
   - Ensure server is running on correct port

3. **Invalid code challenge**
   - Verify PKCE implementation matches Salesforce requirements
   - Check code verifier length (43-128 characters)
   - Ensure proper base64url encoding

4. **Access token expired**
   - Implement refresh token flow
   - Check token expiration times
   - Handle 401 responses gracefully

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Migration from Client Credentials

If migrating from client credentials to PKCE:

1. **Update Connected App:** Enable PKCE, disable client credentials
2. **Update Code:** Replace client credentials auth with PKCE flow
3. **Test Thoroughly:** Ensure OAuth flow works end-to-end
4. **Update Documentation:** Train users on new OAuth flow

## API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger documentation.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Salesforce PKCE documentation
3. Test with sample case data first
4. Check AWS AgentCore logs for issues