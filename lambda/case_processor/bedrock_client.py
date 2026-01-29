#!/usr/bin/env python3
"""
Bedrock Agent Client

Handles all interactions with AWS Bedrock Agent and Knowledge Base.
Encapsulates streaming response handling and error management.
"""

import logging
import os
import time
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 2  # seconds

# Retryable error codes
RETRYABLE_ERRORS = {
    "ThrottlingException",
    "throttlingException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeout",
}


class BedrockAgentError(Exception):
    """Custom exception for Bedrock Agent errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable


class BedrockAgentClient:
    """Client for Bedrock Agent and Knowledge Base operations."""

    def __init__(self) -> None:
        self.region: str = os.environ.get("AWS_REGION", "us-east-1")
        self.agent_id: Optional[str] = os.environ.get("BEDROCK_AGENT_ID")
        self.agent_alias_id: Optional[str] = os.environ.get("BEDROCK_AGENT_ALIAS_ID")
        self.kb_id: Optional[str] = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID")

        # Initialize boto3 client
        self.client: Any = boto3.client("bedrock-agent-runtime", region_name=self.region)

    def invoke_agent(self, prompt: str, session_id: str) -> str:
        """
        Invoke Bedrock Agent with prompt and return response.
        Includes exponential backoff retry for throttling and transient errors.

        Args:
            prompt: The input text for the agent
            session_id: Session ID for conversation continuity

        Returns:
            Agent response as string
            
        Raises:
            BedrockAgentError: If agent invocation fails after retries
            ValueError: If required environment variables are missing
        """
        if not self.agent_id or not self.agent_alias_id:
            raise ValueError("BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID required")

        logger.info(f"Invoking agent {self.agent_id} with session {session_id}")
        last_error: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.invoke_agent(
                    agentId=self.agent_id,
                    agentAliasId=self.agent_alias_id,
                    sessionId=session_id,
                    inputText=prompt,
                )

                # Process streaming response (EventStream)
                result = self._process_streaming_response(response)
                logger.info(f"Agent response length: {len(result)}")
                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                error_message = e.response.get("Error", {}).get("Message", str(e))
                
                if error_code in RETRYABLE_ERRORS and attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)  # 2, 4, 8 seconds
                    logger.warning(
                        f"Retryable error ({error_code}), retrying in {delay}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(delay)
                    last_error = e
                    continue
                    
                # Non-retryable or max retries exceeded
                logger.error(f"Bedrock Agent error: {error_code} - {error_message}")
                raise BedrockAgentError(
                    f"Agent invocation failed: {error_message}",
                    error_code=error_code,
                    retryable=error_code in RETRYABLE_ERRORS
                ) from e
                
            except BotoCoreError as e:
                # Network/connection errors - retry
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Connection error, retrying in {delay}s: {e}")
                    time.sleep(delay)
                    last_error = e
                    continue
                    
                logger.error(f"Bedrock connection error after {MAX_RETRIES} attempts: {e}")
                raise BedrockAgentError(
                    f"Connection failed after {MAX_RETRIES} attempts: {e}",
                    retryable=True
                ) from e
                
            except Exception as e:
                # Unexpected errors - don't retry
                logger.error(f"Unexpected error invoking agent: {e}")
                raise BedrockAgentError(f"Unexpected error: {e}") from e

        # Should not reach here, but handle edge case
        raise BedrockAgentError(
            f"Agent invocation failed after {MAX_RETRIES} attempts",
            retryable=True
        ) from last_error

    def _process_streaming_response(self, response: dict) -> str:
        """
        Process streaming EventStream response from Bedrock Agent.
        
        Args:
            response: Raw response from invoke_agent API
            
        Returns:
            Concatenated response text
        """
        result = ""
        try:
            for event in response.get("completion", []):
                if "chunk" in event:
                    chunk_bytes = event["chunk"].get("bytes")
                    if chunk_bytes:
                        result += chunk_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Error processing streaming response: {e}")
            raise BedrockAgentError(f"Failed to process response stream: {e}") from e
            
        return result

    def search_knowledge_base(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Direct vector search on Knowledge Base.

        Args:
            query: Search query text
            max_results: Maximum number of results to return (1-20)

        Returns:
            List of search results with content, score, and location
            
        Raises:
            BedrockAgentError: If KB search fails
            ValueError: If BEDROCK_KNOWLEDGE_BASE_ID not set
        """
        if not self.kb_id:
            raise ValueError("BEDROCK_KNOWLEDGE_BASE_ID required")

        # Validate max_results
        max_results = max(1, min(max_results, 20))
        
        logger.info(f"KB search: {query[:50]}...")

        try:
            response = self.client.retrieve(
                knowledgeBaseId=self.kb_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": max_results}
                },
            )

            results: list[dict] = []
            for r in response.get("retrievalResults", []):
                results.append(
                    {
                        "content": r.get("content", {}).get("text", ""),
                        "score": r.get("score", 0),
                        "location": r.get("location", {}),
                    }
                )

            logger.info(f"KB search returned {len(results)} results")
            return results
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"KB search error: {error_code} - {error_message}")
            raise BedrockAgentError(
                f"Knowledge Base search failed: {error_message}",
                error_code=error_code
            ) from e
            
        except Exception as e:
            logger.error(f"Unexpected KB search error: {e}")
            raise BedrockAgentError(f"KB search failed: {e}") from e
