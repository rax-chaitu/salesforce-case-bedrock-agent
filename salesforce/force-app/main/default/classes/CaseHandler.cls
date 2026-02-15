/*********************************************************************************

Author: D Anjaneyulu
Date: 09/19/2017
Description: This apex class is created for the Trigger Framework. This class 
controls the flow of execution of the Case trigger.

**********************************************************************************/
public class CaseHandler implements TriggerInterface {
    
    public Boolean isActive()
    {
        if(Trigger_Manager__c.getAll().containsKey('CaseTgr')) {
            return Trigger_Manager__c.getInstance('CaseTgr').Is_Active__c;
        }
        return false;
    }
    
    public void beforeInsert() {
        
    }
    
    public void beforeUpdate() {
        
    }
    
    public void beforeDelete() {}
    
    public void afterInsert()  {
        CaseHelper.updateLocationForPartnerCases();
        //SFDC-6596 - Starts  
        List<Case> partnerCases = new List<Case>();
        Set<Id> caseIds = new Set<Id>();
        for(Case cs : (List<Case>)Trigger.new){
            if(String.isnotblank(cs.AccountId )){
                partnerCases.add(cs);   
            }
        }
        if(!partnerCases.isEmpty()){
            CommunitySharingHelper.shareRecordsOnCreation(partnerCases,'Case');
        }
        //SFDC-6596 - Ends  
        
        // SFDC-XXXXX: Added by Chaitanya - Publish Integration Event for AI Case Analysis
        publishCaseCreatedEvents((List<Case>)Trigger.new);
    }
    
    /**
     * @description Publish Integration_Event__e for new Cases to trigger AWS AI analysis
     */
    private void publishCaseCreatedEvents(List<Case> newCases) {
        List<Integration_Event__e> events = new List<Integration_Event__e>();
        
        for (Case c : newCases) {
            IntegrationEventPublisher.EventData eventData = new IntegrationEventPublisher.EventData();
            eventData.recordId = c.Id;
            eventData.objectName = 'Case';
            eventData.objectRecordType = c.RecordTypeId != null ? 'Case' : 'Case';
            eventData.eventType = IntegrationEventPublisher.EVENT_TYPE_CREATE;
            eventData.changedAttributes = new List<String>{'Subject', 'Description', 'Type', 'Priority'};
            eventData.payload = buildAnalysisPayload(c);

            events.add(eventData.toEvent());
        }
        
        if (!events.isEmpty()) {
            IntegrationEventPublisher.publishEvents(events);
        }
    }
    
    /**
     * @description Build payload with only fields needed for AI analysis — no PII, no system fields
     */
    private Map<String, Object> buildAnalysisPayload(Case c) {
        Map<String, Object> p = new Map<String, Object>();
        p.put('Record_Id__c', c.Id);
        p.put('Case_Number__c', c.CaseNumber);
        p.put('Subject', c.Subject);
        p.put('Description', c.Description);
        p.put('Type', c.Type);
        p.put('Priority', c.Priority);
        p.put('Status', c.Status);
        p.put('Origin', c.Origin);
        p.put('Reason', c.Reason);
        // Case classification
        p.put('Tool__c', c.Tool__c);
        p.put('Support_Reason__c', c.Support_Reason__c);
        p.put('Record_Type__c', c.Record_Type__c);
        p.put('Case_Type__c', c.Case_Type__c);
        p.put('Root_Cause_of_Inquiry__c', c.Root_Cause_of_Inquiry__c);
        // Context
        p.put('Department__c', c.Department__c);
        p.put('Segment__c', c.Segment__c);
        p.put('Business_Justification__c', c.Business_Justification__c);
        p.put('Admin_Notes__c', c.Admin_Notes__c);
        p.put('MRR__c', c.MRR__c);
        p.put('Urgency__c', c.Urgency__c);
        p.put('Commissions_Impacting__c', c.Commissions_Impacting__c);
        // Remove nulls
        Map<String, Object> clean = new Map<String, Object>();
        for (String key : p.keySet()) {
            Object val = p.get(key);
            if (val != null && String.valueOf(val) != '') {
                clean.put(key, val);
            }
        }
        return clean;
    }
    
    public void afterUpdate() {
        
        
    }
    
    public void afterDelete() {
        
    }
    
    public void afterUndelete() {}
}