# Salesforce Connected App Setup Guide

## Purpose
Create a Connected App in Salesforce to allow AWS Lambda to authenticate and update Case records via Salesforce REST API.

---

## Step 1: Create Connected App in Salesforce

### 1.1 Navigate to App Manager
1. Login to Salesforce
2. Setup → Apps → App Manager
3. Click **New Connected App**

### 1.2 Basic Information
- **Connected App Name**: `AWS Bedrock Agent Integration`
- **API Name**: `AWS_Bedrock_Agent_Integration`
- **Contact Email**: your-email@company.com

### 1.3 API (Enable OAuth Settings)
Check **Enable OAuth Settings**

**Callback URL**:
```
https://login.salesforce.com/services/oauth2/callback
```

**Selected OAuth Scopes** (add these):
- `Access the identity URL service (id, profile, email, address, phone)`
- `Manage user data via APIs (api)`
- `Perform requests at any time (refresh_token, offline_access)`
- `Access unique user identifiers (openid)`

**Require Secret for Web Server Flow**: ✅ Checked  
**Require Secret for Refresh Token Flow**: ✅ Checked  
**Enable Client Credentials Flow**: ✅ Checked (if available)

### 1.4 Save
1. Click **Save**
2. Click **Continue**
3. **IMPORTANT**: Copy the **Consumer Key** and **Consumer Secret** immediately

---

## Step 2: Configure Connected App Policies

### 2.1 Manage Connected App
1. Setup → Apps → App Manager
2. Find your app → Click dropdown → **Manage**

### 2.2 Edit Policies
Click **Edit Policies**

**OAuth Policies**:
- **Permitted Users**: `Admin approved users are pre-authorized`
- **IP Relaxation**: `Relax IP restrictions`
- **Refresh Token Policy**: `Refresh token is valid until revoked`

Click **Save**

### 2.3 Manage Profiles
1. Scroll to **Profiles** section
2. Click **Manage Profiles**
3. Select: `System Administrator` (or your integration user's profile)
4. Click **Save**

---

## Step 3: Create Integration User (Recommended)

### 3.1 Create User
1. Setup → Users → New User
2. Configure:
   - **First Name**: `AWS`
   - **Last Name**: `Integration`
   - **Email**: integration-user@company.com
   - **Username**: `aws.integration@yourcompany.com.sandbox`
   - **User License**: `Salesforce`
   - **Profile**: `System Administrator` (or custom profile)
   - **Active**: ✅ Checked

### 3.2 Assign Permission Set (Optional)
Create a permission set with:
- Read/Write access to Case object
- Read access to User object
- API Enabled

---

## Step 4: Test OAuth Flow

### 4.1 Get Access Token
```bash
# Set variables
SF_INSTANCE="https://yourinstance.my.salesforce.com"
CLIENT_ID="your_consumer_key"
CLIENT_SECRET="your_consumer_secret"
USERNAME="aws.integration@yourcompany.com.sandbox"
PASSWORD="your_password"
SECURITY_TOKEN="your_security_token"

# Get access token
curl -X POST "${SF_INSTANCE}/services/oauth2/token" \
  -d "grant_type=password" \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${CLIENT_SECRET}" \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}${SECURITY_TOKEN}"
```

**Response**:
```json
{
  "access_token": "00D...",
  "instance_url": "https://yourinstance.my.salesforce.com",
  "id": "https://login.salesforce.com/id/00D.../005...",
  "token_type": "Bearer",
  "issued_at": "1234567890",
  "signature": "..."
}
```

### 4.2 Test API Call
```bash
ACCESS_TOKEN="your_access_token"
INSTANCE_URL="https://yourinstance.my.salesforce.com"

# Query Cases
curl "${INSTANCE_URL}/services/data/v59.0/query?q=SELECT+Id,CaseNumber,Subject+FROM+Case+LIMIT+1" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
```

---

## Step 5: Store Credentials in AWS Secrets Manager

### 5.1 Create Secret
```bash
export AWS_PROFILE=sandbox4

aws secretsmanager create-secret \
  --name salesforceagent/salesforce/client-secret \
  --description "Salesforce Connected App Client Secret" \
  --secret-string "YOUR_CLIENT_SECRET" \
  --region us-east-1
```

### 5.2 Update Terraform Variables
Edit `terraform/terraform.tfvars`:
```hcl
# Salesforce API Configuration
salesforce_instance_url = "https://yourinstance.my.salesforce.com"
salesforce_client_id    = "YOUR_CONSUMER_KEY"
salesforce_client_secret = "YOUR_CLIENT_SECRET"  # Will be stored in Secrets Manager
```

### 5.3 Apply Terraform
```bash
cd terraform
eval "$(aws configure export-credentials --profile sandbox4 --format env)"
terraform apply -auto-approve
```

---

## Step 6: Update Lambda Environment Variables

The Lambda function needs these environment variables (set by Terraform):
- `SALESFORCE_INSTANCE_URL`: Your Salesforce instance URL
- `SALESFORCE_CLIENT_ID`: Consumer Key from Connected App
- `SALESFORCE_SECRET_ARN`: ARN of secret in Secrets Manager
- `SALESFORCE_USERNAME`: Integration user username
- `SALESFORCE_PASSWORD`: Integration user password (stored in Secrets Manager)

---

## Step 7: Deploy Salesforce Custom Fields

### 7.1 Create Custom Fields on Case Object
1. Setup → Object Manager → Case → Fields & Relationships
2. Click **New**

**Field 1: AI Analysis**
- Data Type: `Long Text Area`
- Field Label: `AI Analysis`
- Field Name: `AI_Analysis__c`
- Length: `32,768`
- Visible Lines: `10`

**Field 2: AI Recommendation**
- Data Type: `Text Area`
- Field Label: `AI Recommendation`
- Field Name: `AI_Recommendation__c`
- Length: `255`

**Field 3: Self Resolvable**
- Data Type: `Checkbox`
- Field Label: `Self Resolvable`
- Field Name: `Self_Resolvable__c`
- Default: `Unchecked`

**Field 4: Similar Cases**
- Data Type: `Long Text Area`
- Field Label: `Similar Cases`
- Field Name: `Similar_Cases__c`
- Length: `32,768`
- Visible Lines: `5`

**Field 5: Estimated Resolution Time**
- Data Type: `Text`
- Field Label: `Estimated Resolution Time`
- Field Name: `Estimated_Resolution_Time__c`
- Length: `50`

### 7.2 Add Fields to Page Layout
1. Setup → Object Manager → Case → Page Layouts
2. Edit your Case Layout
3. Add new fields to the layout
4. Save

---

## Step 8: Deploy Case Trigger

### 8.1 Create Apex Trigger
```apex
trigger CaseAIAnalysisTrigger on Case (after insert) {
    // Only process new cases
    List<Case> newCases = new List<Case>();
    
    for (Case c : Trigger.new) {
        // Add conditions if needed (e.g., specific record types)
        newCases.add(c);
    }
    
    if (!newCases.isEmpty()) {
        CaseAIAnalysisHandler.publishCaseEvents(newCases);
    }
}
```

### 8.2 Create Handler Class
```apex
public class CaseAIAnalysisHandler {
    
    @future
    public static void publishCaseEvents(List<Case> cases) {
        List<Integration_Event__e> events = new List<Integration_Event__e>();
        
        for (Case c : cases) {
            // Build payload
            Map<String, Object> payload = new Map<String, Object>{
                'CaseId' => c.Id,
                'CaseNumber' => c.CaseNumber,
                'Subject' => c.Subject,
                'Description' => c.Description,
                'Priority' => c.Priority,
                'Status' => c.Status
            };
            
            // Create platform event
            Integration_Event__e evt = new Integration_Event__e(
                Object_Name__c = 'Case',
                Type__c = 'CREATE',
                Record_Id__c = c.Id,
                Payload__c = JSON.serialize(payload)
            );
            
            events.add(evt);
        }
        
        // Publish events
        if (!events.isEmpty()) {
            List<Database.SaveResult> results = EventBus.publish(events);
            
            // Log errors
            for (Database.SaveResult result : results) {
                if (!result.isSuccess()) {
                    for (Database.Error error : result.getErrors()) {
                        System.debug('Error publishing event: ' + error.getMessage());
                    }
                }
            }
        }
    }
}
```

### 8.3 Deploy via Salesforce CLI
```bash
cd salesforce

# Deploy trigger
sf project deploy start \
  -d force-app/main/default/triggers/CaseAIAnalysisTrigger.trigger \
  -o UATDEC25

# Deploy handler class
sf project deploy start \
  -d force-app/main/default/classes/CaseAIAnalysisHandler.cls \
  -o UATDEC25
```

---

## Step 9: Test End-to-End Flow

### 9.1 Create Test Case in Salesforce
```apex
// Execute in Developer Console
Case testCase = new Case(
    Subject = 'Test AI Analysis - Cannot login',
    Description = 'User unable to access portal after password reset',
    Priority = 'High',
    Status = 'New'
);
insert testCase;

// Check the case after a few seconds
Case updatedCase = [
    SELECT Id, CaseNumber, AI_Analysis__c, AI_Recommendation__c, 
           Self_Resolvable__c, Similar_Cases__c
    FROM Case 
    WHERE Id = :testCase.Id
];

System.debug('AI Analysis: ' + updatedCase.AI_Analysis__c);
System.debug('Recommendation: ' + updatedCase.AI_Recommendation__c);
```

### 9.2 Monitor Flow
```bash
# Check SQS Queue
aws sqs receive-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/salesforceagent-case-analysis \
  --region us-east-1 \
  --profile sandbox4

# Check Lambda Logs
aws logs tail /aws/lambda/salesforceagent-api --follow --region us-east-1 --profile sandbox4
```

---

## Security Best Practices

1. **Use Integration User**: Don't use personal admin accounts
2. **Restrict IP Ranges**: Configure IP restrictions in Connected App if possible
3. **Rotate Secrets**: Regularly rotate client secret and passwords
4. **Least Privilege**: Grant only necessary permissions to integration user
5. **Monitor API Usage**: Track API calls in Salesforce Setup → System Overview
6. **Enable MFA**: Require MFA for integration user (if using web flow)

---

## Troubleshooting

### Issue: Invalid Client Credentials
- Verify Consumer Key and Secret are correct
- Check if Connected App is approved for the user's profile
- Ensure IP restrictions are relaxed

### Issue: Invalid Username/Password
- Verify username format includes `.sandbox` for sandboxes
- Password must include security token: `password + security_token`
- Check if user is active and has API access

### Issue: Insufficient Privileges
- Verify user has API Enabled permission
- Check object-level permissions (Read/Write on Case)
- Verify field-level security for custom fields

### Issue: Case Fields Not Updating
- Check Lambda logs for errors
- Verify field API names match exactly
- Ensure fields are not read-only or protected

---

## Summary

**What You Need**:
1. Consumer Key (Client ID)
2. Consumer Secret (Client Secret)
3. Integration User Username
4. Integration User Password + Security Token
5. Salesforce Instance URL

**Where to Store**:
- Client ID → `terraform.tfvars` (salesforce_client_id)
- Client Secret → AWS Secrets Manager (via Terraform)
- Instance URL → `terraform.tfvars` (salesforce_instance_url)
- Username/Password → AWS Secrets Manager (optional, for password flow)

**Next Steps**:
1. Update `terraform.tfvars` with Salesforce credentials
2. Run `terraform apply`
3. Deploy Salesforce custom fields
4. Deploy Case trigger and handler
5. Test with a new Case
