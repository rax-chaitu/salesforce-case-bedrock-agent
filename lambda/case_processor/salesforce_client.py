#!/usr/bin/env python3
"""
Salesforce Client - JWT Bearer Token Flow

Matches Glue job authentication pattern:
- Secret: salesforce-{environment}-sandbox-jwt or salesforce-production-jwt
- Format: { "client_id", "username", "private_key" }

Environment Variables:
- SALESFORCE_SECRET_NAME: Secret name (e.g., salesforce-inttest-sandbox-jwt)
- SALESFORCE_ENVIRONMENT: inttest or production (determines auth URL)
"""

import contextlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Optional

import boto3
import jwt
import requests
from simple_salesforce import Salesforce

logger = logging.getLogger(__name__)


class SalesforceClient:
    """
    Salesforce client using JWT Bearer Token flow.
    
    Authentication flow (same as Glue job):
    1. Fetch credentials from Secrets Manager (client_id, username, private_key)
    2. Create JWT signed with private key
    3. Exchange JWT for access token at Salesforce OAuth endpoint
    4. Connect using simple-salesforce with access token
    """
    
    def __init__(self) -> None:
        self.secret_name: str = os.environ.get("SALESFORCE_SECRET_NAME", "")
        self.environment: str = os.environ.get("SALESFORCE_ENVIRONMENT", "inttest")
        
        # Auth URL based on environment (matches Glue pattern)
        self.auth_url: str = (
            "https://login.salesforce.com"
            if self.environment == "production"
            else "https://test.salesforce.com"
        )
        
        self._sf: Optional[Salesforce] = None
        self._credentials: Optional[dict[str, Any]] = None

    def is_configured(self) -> bool:
        """Check if Salesforce integration is configured."""
        return bool(self.secret_name)

    def check_connection(self) -> dict[str, Any]:
        """Test SF JWT auth and return connection status."""
        try:
            conn = self._get_connection()
            if conn:
                # Light query to verify connection works
                conn.query("SELECT Id FROM Organization LIMIT 1")
                return {"connected": True, "instance_url": conn.sf_instance}
            return {"connected": False, "error": "No connection"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def _get_credentials(self) -> dict[str, Any]:
        """
        Fetch credentials from Secrets Manager.
        Format: { "client_id", "username", "private_key" }
        """
        if not self._credentials:
            secrets = boto3.client("secretsmanager")
            response = secrets.get_secret_value(SecretId=self.secret_name)
            self._credentials = json.loads(response["SecretString"])
            logger.info(f"Loaded SF credentials for: {self._credentials.get('username', 'unknown')}")
        return self._credentials

    def _get_access_token(self) -> dict[str, Any]:
        """
        Exchange JWT for Salesforce access token.
        Returns dict with access_token and instance_url.
        """
        creds = self._get_credentials()
        
        # Create JWT (same as Glue job)
        claims: dict[str, Any] = {
            "iss": creds["client_id"],
            "sub": creds["username"],
            "aud": self.auth_url,
            "exp": int(time.time()) + 300,  # 5 min expiry
        }
        jwt_token = jwt.encode(claims, creds["private_key"], algorithm="RS256")
        
        # Exchange for access token
        response = requests.post(
            f"{self.auth_url}/services/oauth2/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        
        token_data: dict[str, Any] = response.json()
        logger.info(f"Got SF token, instance: {token_data.get('instance_url', 'unknown')}")
        return token_data

    def _get_connection(self) -> Optional[Salesforce]:
        """Get or create Salesforce connection."""
        if not self._sf and self.is_configured():
            token_data = self._get_access_token()
            self._sf = Salesforce(
                instance_url=token_data["instance_url"],
                session_id=token_data["access_token"],
                version="62.0",
            )
        return self._sf

    def is_already_analyzed(self, case_id: str) -> bool:
        """
        Check if case was already analyzed today to prevent duplicate processing.
        Returns True if AI_Analysis_Status__c = 'Completed' AND AI_Analyzed_Date__c is today.
        
        NOTE: case_id comes from trusted Salesforce Platform Events, no validation needed.
        """
        sf = self._get_connection()
        if sf is None:
            return False

        if not case_id:
            return False

        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            result = sf.query(
                f"SELECT AI_Analysis_Status__c, AI_Analyzed_Date__c "
                f"FROM Case WHERE Id = '{case_id}'"
            )
            if result["records"]:
                record = result["records"][0]
                status = record.get("AI_Analysis_Status__c")
                analyzed_date = record.get("AI_Analyzed_Date__c", "")

                if status == "Completed" and analyzed_date and analyzed_date.startswith(today):
                    return True
            return False
        except Exception:
            return False

    def update_case_analysis(self, case_id: str, analysis: dict[str, Any]) -> bool:
        """
        Update Salesforce Case with AI analysis results.

        Args:
            case_id: Salesforce Case record ID (18-char)
            analysis: Dict with keys: summary, steps, self_resolvable, similar_cases

        Returns:
            True if update successful
        """
        sf = self._get_connection()
        if sf is None:
            logger.warning(f"Skipping SF update for {case_id} - not connected")
            return False

        try:
            update_data: dict[str, Any] = {
                "AI_Analysis__c": self._format_analysis(analysis),
                "AI_Suggestions__c": self._format_steps(analysis.get("steps", [])),
                "Self_Resolvable__c": analysis.get("self_resolvable", False),
                "Similar_Cases__c": self._format_similar_cases(
                    analysis.get("similar_cases", [])
                ),
                "AI_Analyzed_Date__c": datetime.utcnow().isoformat(),
                "AI_Analysis_Status__c": "Completed",
            }

            sf.Case.update(case_id, update_data)
            logger.info(f"Updated Case {case_id} with analysis")
            return True

        except Exception as e:
            logger.error(f"Failed to update Case {case_id}: {e}")
            with contextlib.suppress(Exception):
                sf.Case.update(
                    case_id,
                    {
                        "AI_Analysis_Status__c": "Failed",
                        "AI_Analysis__c": f"Analysis failed: {e!s}",
                    },
                )
            return False

    def _format_analysis(self, analysis: dict[str, Any]) -> str:
        """Format analysis dict as plain text for Long Text Area field."""
        parts: list[str] = []

        if analysis.get("summary"):
            parts.append(f"SUMMARY\n{analysis['summary']}")

        if analysis.get("root_cause"):
            parts.append(f"ROOT CAUSE\n{analysis['root_cause']}")

        if analysis.get("recommendation"):
            parts.append(f"RECOMMENDATION\n{analysis['recommendation']}")

        if analysis.get("estimated_resolution"):
            parts.append(f"ESTIMATED RESOLUTION\n{analysis['estimated_resolution']}")

        if analysis.get("escalation_needed") and analysis.get("escalation_reason"):
            parts.append(f"ESCALATION REQUIRED\n{analysis['escalation_reason']}")

        if analysis.get("category"):
            parts.append(f"CATEGORY\n{analysis['category']}")

        if analysis.get("kb_articles"):
            articles = analysis["kb_articles"]
            if isinstance(articles, list) and articles:
                articles_text = "\n".join(f"• {a}" for a in articles)
                parts.append(f"KB SOURCES\n{articles_text}")

        parts.append("[AI-Generated Analysis - Please verify before taking action]")

        return "\n\n".join(parts) if parts else json.dumps(analysis, indent=2)

    def _format_steps(self, steps: list[str]) -> str:
        """Format steps list as plain numbered text for Long Text Area field."""
        if not steps:
            return ""
        # Strip any existing numbering from agent response (e.g. "1. Step")
        clean_steps = [re.sub(r'^\d+\.\s*', '', step.strip()) for step in steps]
        formatted = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(clean_steps))
        formatted += "\n\n[AI-Generated Suggestions - Please verify before taking action]"
        return formatted

    def _format_similar_cases(self, cases: list[str]) -> str:
        """Format similar cases as HTML links for Rich Text field."""
        if not cases:
            return ""
        
        # Get instance URL for hyperlinks
        instance_url = ""
        if self._sf:
            instance_url = getattr(self._sf, 'sf_instance', '') or ''
            if instance_url and not instance_url.startswith('http'):
                instance_url = f"https://{instance_url}"
        
        # Collect case numbers to lookup IDs
        case_numbers: list[str] = []
        for case in cases[:5]:
            num_match = re.search(r'#?(\d{8})', case)
            if num_match:
                case_numbers.append(num_match.group(1))
        
        # Lookup Case IDs from Case Numbers
        case_id_map: dict[str, str] = {}
        if case_numbers and self._sf:
            try:
                numbers_str = "','".join(case_numbers)
                result = self._sf.query(
                    f"SELECT Id, CaseNumber FROM Case WHERE CaseNumber IN ('{numbers_str}')"
                )
                for record in result.get("records", []):
                    case_id_map[record["CaseNumber"]] = record["Id"]
            except Exception:
                pass  # Continue without links if lookup fails
        
        formatted_cases: list[str] = []
        for case in cases[:5]:
            # Try to extract Case ID (18-char starting with 500)
            id_match = re.search(r'\b(500[a-zA-Z0-9]{15})\b', case)
            num_match = re.search(r'#?(\d{8})', case)
            
            case_id = None
            display_text = None
            
            if id_match:
                case_id = id_match.group(1)
                display_text = num_match.group(1) if num_match else case_id
            elif num_match:
                case_number = num_match.group(1)
                display_text = case_number
                case_id = case_id_map.get(case_number)
            
            if case_id and instance_url:
                # Create HTML hyperlink
                link = f'<a href="{instance_url}/{case_id}" target="_blank">Case {display_text}</a>'
                # Get description part (after the case reference)
                desc_match = re.search(r':\s*(.+)$', case)
                desc = f": {desc_match.group(1)}" if desc_match else ""
                formatted_cases.append(f"• {link}{desc}")
            else:
                formatted_cases.append(f"• {case}")
        
        return "<br/>".join(formatted_cases)
