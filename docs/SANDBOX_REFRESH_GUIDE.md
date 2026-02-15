# Sandbox Refresh Guide - AI Case Analysis Agent

## Pre-Refresh Backup

Metadata is backed up in `salesforce/force-app/` via:
```bash
sf project retrieve start --manifest salesforce/manifest/package.xml --target-org UATDEC25
```

### What's in the backup (package.xml)

| Type | Components |
|------|-----------|
| CustomField | `AI_Analysis__c`, `AI_Analyzed_Date__c`, `AI_Suggestions__c`, `AI_Analysis_Status__c`, `Self_Resolvable__c`, `Similar_Cases__c`, `AI_Feedback__c`, `AI_Feedback_Comments__c` |
| ApexClass | `CaseHandler` |
| PermissionSet | `AI_Case_Analysis_User`, `AI_Case_Analysis_Integration` |
| PlatformEventChannel | `Case_AI_Analysis_Channel__chn` |
| EventRelayConfig | All event relays |
| NamedCredential | All named credentials |

### What's NOT in the backup (recreate manually)

| Component | Why | How |
|-----------|-----|-----|
| Integration_Event__e | Already exists in prod (survives refresh) | N/A |
| PlatformEventChannelMember | Created via Tooling API script | See Step 3 below |
| Connected App (JWT) | Requires interactive setup | See Step 4 below |
| CaseTrigger | Doesn't exist (CaseHandler called differently) | N/A |

---

## Post-Refresh Steps

### Step 1: Deploy Metadata

```bash
sf project deploy start --manifest salesforce/manifest/package.xml --target-org InttestJune25
```

### Step 2: Assign Permission Sets

```bash
# Integration user (Lambda/API writes AI fields)
sf org assign permset --name AI_Case_Analysis_Integration --on-behalf-of sfdc_tes_admin@rackspace.com.inttest --target-org InttestJune25

# Case agents (read AI fields, edit feedback)
sf org assign permset --name AI_Case_Analysis_User --on-behalf-of <agent_username> --target-org InttestJune25
```

### Step 3: Verify Integration_Event__e Exists

```bash
sf org list metadata -m CustomObject -o InttestJune25 | grep Integration_Event
```

If missing, create it manually in Setup → Platform Events.

### Step 4: Create Platform Event Channel + Member (Tooling API)

Run in Developer Console → Execute Anonymous:

```apex
// Create Channel
HttpRequest req = new HttpRequest();
req.setEndpoint(URL.getOrgDomainUrl().toExternalForm() + '/services/data/v62.0/tooling/sobjects/PlatformEventChannel');
req.setMethod('POST');
req.setHeader('Content-Type', 'application/json');
req.setHeader('Authorization', 'Bearer ' + UserInfo.getSessionId());

Map<String, Object> channelMetadata = new Map<String, Object>{
    'channelType' => 'event',
    'label' => 'Case AI Analysis Channel Sandbox9'
};
Map<String, Object> channelBody = new Map<String, Object>{
    'FullName' => 'Case_AI_Channel_Sandbox9__chn',
    'Metadata' => channelMetadata
};
req.setBody(JSON.serialize(channelBody));

Http http = new Http();
HttpResponse res = http.send(req);
System.debug('Channel Status: ' + res.getStatusCode());
System.debug('Channel Response: ' + res.getBody());
```

Then create the member:

```apex
HttpRequest req = new HttpRequest();
req.setEndpoint(URL.getOrgDomainUrl().toExternalForm() + '/services/data/v62.0/tooling/sobjects/PlatformEventChannelMember');
req.setMethod('POST');
req.setHeader('Content-Type', 'application/json');
req.setHeader('Authorization', 'Bearer ' + UserInfo.getSessionId());

Map<String, Object> memberMetadata = new Map<String, Object>{
    'eventChannel' => 'Case_AI_Channel_Sandbox9__chn',
    'selectedEntity' => 'Integration_Event__e'
};
Map<String, Object> memberBody = new Map<String, Object>{
    'FullName' => 'Case_AI_Channel_Sandbox9_IntegrationEvent',
    'Metadata' => memberMetadata
};
req.setBody(JSON.serialize(memberBody));

Http http = new Http();
HttpResponse res = http.send(req);
System.debug('Member Status: ' + res.getStatusCode());
System.debug('Member Response: ' + res.getBody());
```

### Step 5: Connected App (JWT)

1. Setup → App Manager → Find or create Connected App
2. Enable OAuth: scopes `api`, `refresh_token`
3. Check "Use digital signatures" → Upload `salesforce.crt`
4. Manage → Edit Policies → "Admin approved users are pre-authorized"
5. Add integration user's profile
6. Copy Consumer Key

### Step 6: Create Event Relay

1. Setup → Event Relays → New
   - Label: `AWS_Sandbox9_Case_AI` (or appropriate name)
   - Event Channel: Select the channel created in Step 3
   - State: `STOP`
2. Save → Copy Partner Event Source ARN

### Step 7: Associate Partner Event Bus in AWS

```bash
EVENT_SOURCE="aws.partner/salesforce.com/00DgP.../0YLgP..."

aws events create-event-bus \
  --name "$EVENT_SOURCE" \
  --event-source-name "$EVENT_SOURCE" \
  --region us-east-1 --profile SANDBOX9FEB9
```

### Step 8: Update Terraform + Deploy

```hcl
# terraform.tfvars
salesforce_event_source = "aws.partner/salesforce.com/00DgP.../0YLgP..."
```

```bash
cd terraform && terraform apply
```

### Step 9: Start Event Relay

1. Setup → Event Relays → Open relay
2. Change State: `STOP` → `RUN`

### Step 10: Update AWS Secret (if username changed)

```bash
aws secretsmanager put-secret-value \
  --secret-id salesforce-inttest-sandbox-jwt \
  --secret-string '{"client_id":"NEW_KEY","username":"NEW_USER","private_key":"..."}' \
  --profile SANDBOX9FEB9 --region us-east-1
```

### Step 11: Verify

```bash
# Health check
awscurl --service execute-api --region us-east-1 "$API_URL/health"

# Create test case
sf data create record --sobject Case \
  --values "Subject='Test AI Analysis' Description='Test after refresh' Priority='High' Origin='Web'" \
  --target-org InttestJune25 --json
```
