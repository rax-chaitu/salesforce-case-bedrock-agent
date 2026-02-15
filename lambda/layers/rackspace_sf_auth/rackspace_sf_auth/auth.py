"""
Rackspace Salesforce Auth - JWT Bearer Token Flow

Reusable Lambda Layer for Salesforce authentication.
Any Lambda can attach this layer and import:
    from rackspace_sf_auth import SalesforceAuthClient

Authentication flow (matches Glue job pattern):
1. Fetch credentials from Secrets Manager (client_id, username, private_key)
2. Create JWT signed with private key
3. Exchange JWT for access token at Salesforce OAuth endpoint
4. Return simple-salesforce connection or raw token

Secret naming: salesforce-{env}-sandbox-jwt or salesforce-production-jwt
Secret format: { "client_id", "username", "private_key" }
"""

import json
import logging
import os
import time
from typing import Any, Optional

import boto3
import jwt
import requests
from simple_salesforce import Salesforce

logger = logging.getLogger(__name__)


class SalesforceAuthClient:
    """
    Salesforce JWT Bearer Token authentication client.

    Usage:
        client = SalesforceAuthClient()
        sf = client.get_connection()       # simple-salesforce instance
        token = client.get_access_token()  # raw {access_token, instance_url}
    """

    def __init__(
        self,
        secret_name: str = "",
        environment: str = "",
    ) -> None:
        self.secret_name = secret_name or os.environ.get("SALESFORCE_SECRET_NAME", "")
        self.environment = environment or os.environ.get("SALESFORCE_ENVIRONMENT", "inttest")
        self.auth_url = (
            "https://login.salesforce.com"
            if self.environment == "production"
            else "https://test.salesforce.com"
        )
        self._sf: Optional[Salesforce] = None
        self._credentials: Optional[dict[str, Any]] = None

    def is_configured(self) -> bool:
        """Check if Salesforce integration is configured."""
        return bool(self.secret_name)

    def get_connection(self) -> Optional[Salesforce]:
        """Get or create simple-salesforce connection."""
        if not self._sf and self.is_configured():
            token_data = self.get_access_token()
            self._sf = Salesforce(
                instance_url=token_data["instance_url"],
                session_id=token_data["access_token"],
                version="62.0",
            )
        return self._sf

    def get_access_token(self) -> dict[str, Any]:
        """
        Exchange JWT for Salesforce access token.
        Returns: {"access_token": "...", "instance_url": "..."}
        """
        creds = self._get_credentials()
        claims = {
            "iss": creds["client_id"],
            "sub": creds["username"],
            "aud": self.auth_url,
            "exp": int(time.time()) + 300,
        }
        jwt_token = jwt.encode(claims, creds["private_key"], algorithm="RS256")

        response = requests.post(
            f"{self.auth_url}/services/oauth2/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        token_data = response.json()
        logger.info(f"SF auth success, instance: {token_data.get('instance_url', 'unknown')}")
        return token_data

    def check_connection(self) -> dict[str, Any]:
        """Test connection and return status."""
        try:
            conn = self.get_connection()
            if conn:
                conn.query("SELECT Id FROM Organization LIMIT 1")
                return {"connected": True, "instance_url": conn.sf_instance}
            return {"connected": False, "error": "No connection"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def _get_credentials(self) -> dict[str, Any]:
        """Fetch credentials from Secrets Manager."""
        if not self._credentials:
            secrets = boto3.client("secretsmanager")
            response = secrets.get_secret_value(SecretId=self.secret_name)
            self._credentials = json.loads(response["SecretString"])
            logger.info(f"Loaded SF credentials for: {self._credentials.get('username', 'unknown')}")
        return self._credentials
