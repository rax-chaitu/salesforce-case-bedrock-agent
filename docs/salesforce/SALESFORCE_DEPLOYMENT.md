# Salesforce Components Deployment Guide

This guide explains how to deploy the AgentCore integration components to your Salesforce org.

## Components Overview

### Apex Classes
- `AgentCoreService.cls` - Service class for API integration with AWS AgentCore
- `CaseAnalysisController.cls` - Controller for Lightning Web Component

### Lightning Web Component
- `caseAnalysis` - Interactive component for case analysis and escalation checks

## Prerequisites

1. **Salesforce Org** with Lightning Experience enabled
2. **API access** enabled in your org
3. **Remote Site Settings** configured for your AWS API endpoint
4. **System Administrator** or **Developer** permissions

## Deployment Steps

### Step 1: Configure Remote Site Settings

1. Go to **Setup** → **Security** → **Remote Site Settings**
2. Click **New Remote Site**
3. Configure:
   - **Remote Site Name:** `AgentCore_API`
   - **Remote Site URL:** `https://your-api-domain.com` (replace with your deployed API URL)
   - **Active:** ✅ Checked
   - **Disable Protocol Security:** ❌ Unchecked (keep HTTPS)

### Step 2: Deploy Apex Classes

#### Option A: Developer Console
1. Open **Developer Console**
2. File → New → Apex Class
3. Create `AgentCoreService` and paste the code from `AgentCoreService.cls`
4. Create `CaseAnalysisController` and paste the code from `CaseAnalysisController.cls`
5. Save both classes

#### Option B: VS Code with Salesforce Extension
1. Install **Salesforce Extension Pack** in VS Code
2. Create new SFDX project: `sfdx project:create -n AgentCoreIntegration`
3. Copy Apex classes to `force-app/main/default/classes/`
4. Deploy: `sfdx force:source:deploy -p force-app/main/default/classes/`

#### Option C: Workbench or Metadata API
1. Create deployment package with the Apex classes
2. Use Workbench migration tool or Salesforce CLI

### Step 3: Deploy Lightning Web Component

#### Option A: VS Code with Salesforce Extension
1. Copy the `lwc/caseAnalysis` folder to your SFDX project
2. Deploy: `sfdx force:source:deploy -p force-app/main/default/lwc/caseAnalysis/`

#### Option B: Developer Console (for Aura components)
Note: LWC requires VS Code deployment or Salesforce CLI

### Step 4: Update API Endpoint

1. Open `AgentCoreService.cls` in your org
2. Update line 9:
   ```apex
   private static final String AGENTCORE_BASE_URL = 'https://YOUR_ACTUAL_API_URL';
   ```
3. Replace with your deployed AWS API URL

### Step 5: Add Component to Case Page

1. Go to **Setup** → **Object Manager** → **Case**
2. Click **Lightning Record Pages**
3. Choose your Case record page or create new one
4. **Edit Page** in Lightning App Builder
5. From **Custom** components, drag **AI Case Analysis** to the page
6. **Save** and **Activate** the page

### Step 6: Set Permissions

1. Go to **Setup** → **Users** → **Permission Sets** (or Profiles)
2. Create new Permission Set: "AgentCore Users"
3. **Apex Class Access:**
   - AgentCoreService: ✅ Enabled
   - CaseAnalysisController: ✅ Enabled
4. **System Permissions:**
   - API Enabled: ✅ Enabled
5. Assign to users who will use the AI analysis

## Testing the Integration

### 1. Test API Connection
1. Navigate to any Case record
2. Find the **AI Case Analysis** component
3. Click **Test Connection**
4. Should show "Connected" status

### 2. Test Case Analysis
1. Open a Case with description and details
2. Click **Analyze Case**
3. Review the AI analysis results
4. Optionally click **Apply Recommendations**

### 3. Test Escalation Check
1. Click **Check Escalation**
2. Review escalation assessment
3. If escalation recommended, click **Escalate Case**

## Troubleshooting

### Common Issues

1. **"Unauthorized endpoint" error**
   - Check Remote Site Settings configuration
   - Ensure HTTPS URL is used

2. **"Method not found" error**
   - Verify Apex classes deployed correctly
   - Check class and method names

3. **Component not visible**
   - Confirm component is added to page layout
   - Check user permissions

4. **API timeout**
   - Increase timeout in `AgentCoreService.cls`
   - Check AWS API performance

### Debug Steps

1. **Check Debug Logs:**
   - Setup → Environments → Logs → Debug Logs
   - Add trace flag for your user
   - Run test and review logs

2. **Use Developer Console:**
   - Execute Anonymous Apex to test:
   ```apex
   AgentCoreService.ApiResponse result = AgentCoreService.testConnection();
   System.debug(result);
   ```

3. **Check Network Tab:**
   - Open browser Developer Tools
   - Monitor network requests for errors

## Configuration Options

### Custom Fields (Optional)
Consider adding these custom fields to Case object:
- `AI_Analysis__c` (Long Text Area) - Store full AI analysis
- `Escalation_Recommended__c` (Checkbox) - Track AI escalation recommendations
- `AI_Session_ID__c` (Text) - Store session IDs for audit

### Workflow Rules (Optional)
Create workflow rules to:
- Auto-assign cases when escalation is recommended
- Send email alerts for high-priority AI recommendations
- Update case status based on AI analysis

## Security Considerations

1. **API Endpoint Security:**
   - Use HTTPS only
   - Implement API authentication if needed
   - Restrict access by IP if possible

2. **Salesforce Security:**
   - Limit permission set assignments
   - Use field-level security for sensitive data
   - Monitor debug logs for sensitive information

3. **Data Privacy:**
   - Review what case data is sent to AI
   - Ensure compliance with data protection regulations
   - Consider data retention policies

## Production Deployment Checklist

- [ ] Remote Site Settings configured
- [ ] Apex classes deployed and tested
- [ ] LWC deployed and added to page layouts
- [ ] API endpoint updated with production URL
- [ ] Permissions configured for end users
- [ ] Integration tested end-to-end
- [ ] Debug logging configured appropriately
- [ ] Security review completed
- [ ] User training completed

## Support

For technical issues:
1. Check Salesforce debug logs
2. Verify AWS API functionality
3. Test with simple cases first
4. Review error messages in component

## Sample Test Cases

Use these for testing:

**Test Case 1: Simple Issue**
- Subject: "Password reset not working"
- Description: "User cannot reset password using forgot password link"
- Priority: Medium

**Test Case 2: Complex Issue**
- Subject: "Critical system down - production impact"
- Description: "Main application server is down, affecting 500+ users. Revenue impact estimated at $10k/hour"
- Priority: High

**Test Case 3: Escalation Test**
- Subject: "Customer threatening to cancel contract"
- Description: "VIP customer having recurring issues for 2 weeks, contract worth $2M annually"
- Priority: High