#!/usr/bin/env python3
"""
KAV Sync Lambda - Daily sync of Salesforce Knowledge Articles to S3 + Bedrock KB

Triggered by EventBridge schedule (daily).
Uses existing JWT auth from salesforce_client.
"""

import json
import logging
import os
import re
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Import salesforce client from case_processor (shared code)
import sys
sys.path.insert(0, '/var/task')
from salesforce_client import SalesforceClient


def lambda_handler(event, context):
    """
    Main handler - sync KAV to S3 and trigger KB ingestion.
    """
    try:
        # Config from environment
        s3_bucket = os.environ.get('S3_BUCKET')
        s3_key = os.environ.get('S3_KEY', 'kav_articles.txt')
        kb_id = os.environ.get('KNOWLEDGE_BASE_ID')
        data_source_id = os.environ.get('DATA_SOURCE_ID')
        
        if not all([s3_bucket, kb_id, data_source_id]):
            raise ValueError("Missing required env vars: S3_BUCKET, KNOWLEDGE_BASE_ID, DATA_SOURCE_ID")
        
        # Initialize clients
        sf = SalesforceClient()
        s3 = boto3.client('s3')
        bedrock = boto3.client('bedrock-agent')
        
        # Query published KAV articles
        logger.info("Querying KAV articles from Salesforce...")
        kav_records = query_kav_articles(sf)
        logger.info(f"Found {len(kav_records)} published KAV articles")
        
        if not kav_records:
            logger.warning("No KAV articles found, skipping sync")
            return {"statusCode": 200, "body": "No articles to sync"}
        
        # Transform to text format for KB
        content = transform_to_text(kav_records)
        
        # Upload to S3
        logger.info(f"Uploading to s3://{s3_bucket}/{s3_key}")
        s3.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=content.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Trigger KB sync
        logger.info(f"Starting KB ingestion job for {kb_id}/{data_source_id}")
        response = bedrock.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id
        )
        job_id = response['ingestionJob']['ingestionJobId']
        logger.info(f"Ingestion job started: {job_id}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "KAV sync completed",
                "articles_synced": len(kav_records),
                "s3_location": f"s3://{s3_bucket}/{s3_key}",
                "ingestion_job_id": job_id,
                "timestamp": datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"KAV sync failed: {str(e)}")
        raise


def query_kav_articles(sf_client):
    """Query published Knowledge Articles from Salesforce."""
    query = """
        SELECT Id, ArticleNumber, Title, Question__c, Answer__c, Summary, 
               PublishStatus, LastPublishedDate 
        FROM Knowledge__kav 
        WHERE PublishStatus = 'Online' AND Language = 'en_US'
    """
    
    # Use the SF client's connection
    sf = sf_client._get_client()
    result = sf.query(query)
    return result.get('records', [])


def clean_html(text):
    """Remove HTML tags and clean whitespace."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def transform_to_text(records):
    """Transform KAV records to text format for KB indexing."""
    articles = []
    
    for r in records:
        article = f"""
---
Article Number: {r.get('ArticleNumber', 'N/A')}
Title: {r.get('Title', 'N/A')}
Question: {clean_html(r.get('Question__c'))}
Answer: {clean_html(r.get('Answer__c'))}
Summary: {r.get('Summary') or 'N/A'}
Last Published: {r.get('LastPublishedDate', 'N/A')}
---
"""
        articles.append(article)
    
    return '\n'.join(articles)
