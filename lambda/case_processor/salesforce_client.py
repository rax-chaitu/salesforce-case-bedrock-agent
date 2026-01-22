#!/usr/bin/env python3
"""
Salesforce Client - JWT Bearer Token Flow

Environment Variables:
- SALESFORCE_INSTANCE_URL
- SALESFORCE_CLIENT_ID
- SALESFORCE_USERNAME
- SALESFORCE_PRIVATE_KEY_ARN
"""

import contextlib
import json
import logging
import os
import time
from datetime import datetime

import boto3
import jwt
import requests
from simple_salesforce import Salesforce

logger = logging.getLogger(__name__)


class SalesforceClient:
    def __init__(self):
        self.instance_url = os.environ.get("SALESFORCE_INSTANCE_URL", "")
        self.client_id = os.environ.get("SALESFORCE_CLIENT_ID", "")
        self.username = os.environ.get("SALESFORCE_USERNAME", "")
        self.private_key_arn = os.environ.get("SALESFORCE_PRIVATE_KEY_ARN", "")
        self.login_url = (
            "https://test.salesforce.com"
            if "sandbox" in self.instance_url
            else "https://login.salesforce.com"
        )

        self._sf = None
        self._private_key = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.username and self.private_key_arn)

    def _get_private_key(self):
        if not self._private_key:
            secrets = boto3.client("secretsmanager")
            self._private_key = secrets.get_secret_value(SecretId=self.private_key_arn)[
                "SecretString"
            ]
        return self._private_key

    def _get_access_token(self):
        payload = {
            "iss": self.client_id,
            "sub": self.username,
            "aud": self.login_url,
            "exp": int(time.time()) + 180,
        }
        jwt_token = jwt.encode(payload, self._get_private_key(), algorithm="RS256")

        resp = requests.post(
            f"{self.login_url}/services/oauth2/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _get_connection(self):
        if not self._sf and self.is_configured():
            self._sf = Salesforce(
                instance_url=self.instance_url, session_id=self._get_access_token()
            )
        return self._sf

    def update_case_analysis(self, case_id: str, analysis: dict) -> bool:
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
            # Build update payload
            update_data = {
                "AI_Analysis__c": self._format_analysis(analysis),
                "AI_Suggestions__c": self._format_steps(analysis.get("steps", [])),
                "Self_Resolvable__c": analysis.get("self_resolvable", False),
                "Similar_Cases__c": self._format_similar_cases(
                    analysis.get("similar_cases", [])
                ),
                "AI_Analyzed_Date__c": datetime.utcnow().isoformat(),
                "Agent_Analysis_Status__c": "Completed",
            }

            # Update Case record
            sf.Case.update(case_id, update_data)
            logger.info(f"Updated Case {case_id} with analysis")
            return True

        except Exception as e:
            logger.error(f"Failed to update Case {case_id}: {e}")
            # Try to mark as failed
            with contextlib.suppress(Exception):
                sf.Case.update(
                    case_id,
                    {
                        "Agent_Analysis_Status__c": "Failed",
                        "AI_Analysis__c": f"Analysis failed: {e!s}",
                    },
                )
            return False

    def _format_analysis(self, analysis: dict) -> str:
        """Format analysis dict as readable text for Long Text Area field."""
        parts = []

        if analysis.get("summary"):
            parts.append(f"## Summary\n{analysis['summary']}")

        if analysis.get("recommendation"):
            parts.append(f"## Recommendation\n{analysis['recommendation']}")

        if analysis.get("estimated_resolution"):
            parts.append(f"## Estimated Resolution\n{analysis['estimated_resolution']}")

        return "\n\n".join(parts) if parts else json.dumps(analysis, indent=2)

    def _format_steps(self, steps: list) -> str:
        """Format steps list as numbered text."""
        if not steps:
            return ""
        return "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps))

    def _format_similar_cases(self, cases: list) -> str:
        """Format similar cases as bullet list."""
        if not cases:
            return ""
        return "\n".join(f"• {case}" for case in cases[:5])  # Limit to 5
