output "agent_id" {
  description = "The ID of the Bedrock Agent"
  value       = aws_bedrockagent_agent.salesforce_agent.agent_id
}

output "agent_arn" {
  description = "The ARN of the Bedrock Agent"
  value       = aws_bedrockagent_agent.salesforce_agent.agent_arn
}

output "dev_alias_id" {
  description = "The ID of the development alias"
  value       = aws_bedrockagent_agent_alias.dev_alias.agent_alias_id
}

output "prod_alias_id" {
  description = "The ID of the production alias"
  value       = aws_bedrockagent_agent_alias.prod_alias.agent_alias_id
}

output "agent_role_arn" {
  description = "The ARN of the agent's IAM role"
  value       = aws_iam_role.bedrock_agent_role.arn
}
