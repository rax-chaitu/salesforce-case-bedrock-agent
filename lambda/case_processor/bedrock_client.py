#!/usr/bin/env python3
"""
Bedrock Agent Client

Handles all interactions with AWS Bedrock Agent and Knowledge Base.
Encapsulates streaming response handling and error management.
"""

import logging
import os

import boto3

logger = logging.getLogger(__name__)


class BedrockAgentClient:
    """Client for Bedrock Agent and Knowledge Base operations."""

    def __init__(self):
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.agent_id = os.environ.get("BEDROCK_AGENT_ID")
        self.agent_alias_id = os.environ.get("BEDROCK_AGENT_ALIAS_ID")
        self.kb_id = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID")

        # Initialize boto3 client
        self.client = boto3.client("bedrock-agent-runtime", region_name=self.region)

    def invoke_agent(self, prompt: str, session_id: str) -> str:
        """
        Invoke Bedrock Agent with prompt and return response.

        Args:
            prompt: The input text for the agent
            session_id: Session ID for conversation continuity

        Returns:
            Agent response as string
        """
        if not self.agent_id or not self.agent_alias_id:
            raise ValueError("BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID required")

        logger.info(f"Invoking agent {self.agent_id} with session {session_id}")

        response = self.client.invoke_agent(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            sessionId=session_id,
            inputText=prompt,
        )

        # Process streaming response (EventStream)
        result = ""
        for event in response["completion"]:
            if "chunk" in event:
                chunk_bytes = event["chunk"].get("bytes")
                if chunk_bytes:
                    result += chunk_bytes.decode("utf-8")

        logger.info(f"Agent response length: {len(result)}")
        return result

    def search_knowledge_base(self, query: str, max_results: int = 5) -> list:
        """
        Direct vector search on Knowledge Base.

        Args:
            query: Search query text
            max_results: Maximum number of results to return

        Returns:
            List of search results with content, score, and location
        """
        if not self.kb_id:
            raise ValueError("BEDROCK_KNOWLEDGE_BASE_ID required")

        logger.info(f"KB search: {query[:50]}...")

        response = self.client.retrieve(
            knowledgeBaseId=self.kb_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": max_results}
            },
        )

        results = []
        for r in response.get("retrievalResults", []):
            results.append(
                {
                    "content": r.get("content", {}).get("text", ""),
                    "score": r.get("score", 0),
                    "location": r.get("location", {}),
                }
            )

        return results
