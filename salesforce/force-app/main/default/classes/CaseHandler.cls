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
            eventData.payload = new Map<String, Object>{
                'Case_Number__c' => c.CaseNumber,
                'Subject' => c.Subject,
                'Description' => c.Description,
                'Type' => c.Type,
                'Priority' => c.Priority,
                'Record_Id__c' => c.Id,
                'Tool__c' => c.Tool__c,
                'Support_Reason__c' => c.Support_Reason__c,
                'Reason' => c.Reason,
                'Record_Type__c' => c.Record_Type__c,
                'Status' => c.Status,
                'Origin' => c.Origin,
                'Root_Cause_of_Inquiry__c' => c.Root_Cause_of_Inquiry__c,
                'Case_Type__c' => c.Case_Type__c,
                'Department__c' => c.Department__c,
                'Segment__c' => c.Segment__c,
                'OpportunityNumber__c' => c.OpportunityNumber__c
            };

            events.add(eventData.toEvent());
        }
        
        if (!events.isEmpty()) {
            IntegrationEventPublisher.publishEvents(events);
        }
    }
    
    public void afterUpdate() {
        
        
    }
    
    public void afterDelete() {
        
    }
    
    public void afterUndelete() {}
}