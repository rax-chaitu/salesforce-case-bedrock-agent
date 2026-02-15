#!/usr/bin/env python3
"""
SOP to Knowledge Article Converter
Analyzes SOP documents and creates well-structured KA records for Salesforce import.
"""

import os
import csv
import re
from docx import Document
from datetime import datetime

SOP_DIR = os.path.expanduser("~/Downloads/SFDC SOP Files")
OUTPUT_DIR = os.path.expanduser("~/Downloads")

def extract_docx_content(filepath):
    """Extract structured content from a docx file"""
    try:
        doc = Document(filepath)
        content = {
            'paragraphs': [],
            'tables': [],
            'steps': [],
            'notes': [],
            'links': []
        }
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Identify steps
            if re.match(r'^(Step\s*\d+|Part\s*\d+|\d+\.|\d+\))', text, re.IGNORECASE):
                content['steps'].append(text)
            # Identify notes/important info
            elif text.lower().startswith(('note:', 'important:', 'tip:', 'warning:')):
                content['notes'].append(text)
            # Extract links
            elif 'http' in text or 'https' in text:
                content['links'].append(text)
                content['paragraphs'].append(text)
            else:
                content['paragraphs'].append(text)
        
        # Extract table content
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_text:
                    table_data.append(' | '.join(row_text))
            if table_data:
                content['tables'].append('\n'.join(table_data))
        
        return content
    except Exception as e:
        return {'error': str(e), 'paragraphs': [], 'tables': [], 'steps': [], 'notes': [], 'links': []}

def analyze_and_create_ka(filepath, filename, category):
    """Analyze SOP content and create a well-structured KA record"""
    
    content = extract_docx_content(filepath)
    
    if 'error' in content:
        return None
    
    # Clean title from filename
    title = os.path.splitext(filename)[0]
    title = re.sub(r'\s*SOP\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'^\s*SOP\s+', '', title, flags=re.IGNORECASE)
    title = title.strip()
    
    # Generate meaningful question based on content analysis
    question = generate_question(title, category, content)
    
    # Generate structured answer
    answer = generate_answer(title, content)
    
    # Generate summary
    summary = generate_summary(title, content)
    
    # Generate URL-safe name
    url_name = generate_url_name(title)
    
    return {
        'Title': title,
        'UrlName': url_name,
        'Question__c': question,
        'Answer__c': answer,
        'Summary': summary,
        'Category': category,
        'Language': 'en_US',
        'SourceFile': filename
    }

def generate_question(title, category, content):
    """Generate a meaningful question based on the SOP content"""
    
    title_lower = title.lower()
    
    # Pattern matching for common SOP types
    if any(word in title_lower for word in ['creation', 'create', 'new']):
        return f"How do I create a new {extract_object_name(title)} in Salesforce?"
    
    elif any(word in title_lower for word in ['sync', 'syncing']):
        return f"How do I sync {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['merge', 'merging']):
        return f"How do I merge {extract_object_name(title)} in Salesforce?"
    
    elif any(word in title_lower for word in ['approval', 'approve']):
        return f"What is the approval process for {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['upload', 'import']):
        return f"How do I upload or import {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['reject', 'rejection']):
        return f"How do I reject a {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['termination', 'deactivate', 'remove']):
        return f"How do I handle {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['access', 'license', 'permission']):
        return f"How do I grant or manage {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['error', 'troubleshoot', 'issue']):
        return f"How do I troubleshoot {extract_object_name(title)}?"
    
    elif any(word in title_lower for word in ['update', 'change', 'modify']):
        return f"How do I update or change {extract_object_name(title)}?"
    
    elif 'how to' in title_lower:
        return title + "?"
    
    else:
        # Default question format based on category
        if category == 'Accounts':
            return f"How do I manage {title} for Accounts?"
        elif category == 'Companies':
            return f"How do I handle {title} for Companies?"
        elif category == 'Opportunities':
            return f"What is the process for {title}?"
        elif category == 'Leads':
            return f"How do I manage {title} for Leads?"
        elif category == 'Tools Access':
            return f"How do I configure or access {title}?"
        else:
            return f"What is the process for {title}?"

def extract_object_name(title):
    """Extract the main object/subject from the title"""
    # Remove common prefixes/suffixes
    cleaned = re.sub(r'\b(SOP|How to|Process|Steps|Guide)\b', '', title, flags=re.IGNORECASE)
    cleaned = cleaned.strip(' -:')
    return cleaned if cleaned else title

def generate_answer(title, content):
    """Generate a well-structured answer from the SOP content"""
    
    answer_parts = []
    
    # Add overview from first paragraphs (skip title-like first paragraph)
    overview_paras = []
    for para in content['paragraphs'][:5]:
        # Skip if it's just the title repeated
        if para.lower().strip() == title.lower().strip():
            continue
        # Skip very short paragraphs that might be headers
        if len(para) < 20 and not any(char.isdigit() for char in para):
            continue
        overview_paras.append(para)
        if len(overview_paras) >= 2:
            break
    
    if overview_paras:
        answer_parts.append("OVERVIEW:\n" + '\n'.join(overview_paras))
    
    # Add steps if available
    if content['steps']:
        answer_parts.append("\nSTEPS:\n" + '\n'.join(content['steps']))
    
    # Add remaining content (excluding what we already used)
    remaining = []
    used_text = set(overview_paras + content['steps'] + content['notes'])
    for para in content['paragraphs']:
        if para not in used_text and len(para) > 30:
            remaining.append(para)
    
    if remaining:
        # Limit to avoid too long content
        remaining_text = '\n'.join(remaining[:10])
        if remaining_text:
            answer_parts.append("\nADDITIONAL INFORMATION:\n" + remaining_text)
    
    # Add notes/important info
    if content['notes']:
        answer_parts.append("\nIMPORTANT NOTES:\n" + '\n'.join(content['notes']))
    
    # Add table info if relevant
    if content['tables']:
        table_text = '\n'.join(content['tables'][:2])  # Limit tables
        if table_text:
            answer_parts.append("\nREFERENCE DATA:\n" + table_text)
    
    # Combine all parts
    full_answer = '\n\n'.join(answer_parts)
    
    # Clean up excessive whitespace
    full_answer = re.sub(r'\n{3,}', '\n\n', full_answer)
    full_answer = re.sub(r' {2,}', ' ', full_answer)
    
    # Truncate if too long (SF has limits)
    if len(full_answer) > 30000:
        full_answer = full_answer[:30000] + "\n\n[Content truncated - see original SOP for complete details]"
    
    return full_answer.strip()

def generate_summary(title, content):
    """Generate a concise summary for the KA"""
    
    # Try to get first meaningful paragraph
    for para in content['paragraphs'][:5]:
        if len(para) > 50 and len(para) < 500:
            # Clean and truncate
            summary = para.strip()
            if len(summary) > 250:
                summary = summary[:247] + "..."
            return summary
    
    # Fallback: generate from title
    return f"Standard Operating Procedure for {title} in Salesforce."

def generate_url_name(title):
    """Generate URL-safe name"""
    url = re.sub(r'[^a-zA-Z0-9\s-]', '', title)
    url = re.sub(r'\s+', '-', url).strip('-')
    return url[:80]

def categorize_sop(filepath):
    """Determine category based on folder structure"""
    path_str = str(filepath)
    
    if '/Knowledge Articles/' in path_str:
        return 'Knowledge Articles'
    elif '/Opportunities/' in path_str:
        return 'Opportunities'
    elif '/Leads/' in path_str:
        return 'Leads'
    elif '/Tools Access/' in path_str:
        return 'Tools Access'
    elif '/Accounts/' in path_str:
        return 'Accounts'
    elif '/Companies/' in path_str:
        return 'Companies'
    elif '/Users/' in path_str:
        return 'Users'
    elif '/Revegy' in path_str:
        return 'Tools Access'
    else:
        return 'General'

def main():
    """Main function to process all SOPs"""
    
    # Collect all docx files
    docx_files = []
    for root, dirs, files in os.walk(SOP_DIR):
        for file in files:
            if file.endswith('.docx') and not file.startswith('~$'):
                docx_files.append(os.path.join(root, file))
    
    print(f"Found {len(docx_files)} SOP documents to analyze")
    print("=" * 60)
    
    # Process files
    records = []
    errors = []
    
    for filepath in sorted(docx_files):
        filename = os.path.basename(filepath)
        category = categorize_sop(filepath)
        
        print(f"Analyzing: {filename[:50]}...")
        
        ka_record = analyze_and_create_ka(filepath, filename, category)
        
        if ka_record:
            records.append(ka_record)
            print(f"  ✓ Created KA: {ka_record['Title'][:40]}... [{category}]")
        else:
            errors.append(filename)
            print(f"  ✗ Error processing: {filename}")
    
    # Write CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = os.path.join(OUTPUT_DIR, f"SFDC_Knowledge_Articles_{timestamp}.csv")
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Title', 'UrlName', 'Question__c', 'Answer__c', 'Summary', 'Category', 'Language', 'SourceFile']
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(records)
    
    # Print summary
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(f"Total SOPs processed: {len(docx_files)}")
    print(f"KA records created: {len(records)}")
    print(f"Errors: {len(errors)}")
    
    # Category breakdown
    categories = {}
    for r in records:
        cat = r['Category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nBy Category:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat:25} {count:3} articles")
    
    print(f"\n✅ CSV saved to: {output_csv}")
    
    if errors:
        print(f"\n⚠️  Files with errors: {', '.join(errors)}")
    
    return output_csv

if __name__ == "__main__":
    main()
