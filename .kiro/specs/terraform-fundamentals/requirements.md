# Requirements Document

## Introduction

This specification defines a learning curriculum for Terraform fundamentals, designed specifically for Salesforce developers who are new to Infrastructure as Code (IaC). The curriculum uses Salesforce analogies throughout to bridge familiar concepts with Terraform equivalents, enabling faster comprehension and practical application.

The target learner is a Senior Salesforce Developer with 6+ years of Salesforce experience but no prior Terraform knowledge. The curriculum uses their existing Salesforce Bedrock Agent project as a hands-on learning environment.

## Glossary

- **Terraform**: An Infrastructure as Code (IaC) tool that defines and provisions cloud infrastructure using declarative configuration files
- **Provider**: A Terraform plugin that enables interaction with a specific cloud platform (e.g., AWS, Azure, GCP)
- **Resource**: A single infrastructure component managed by Terraform (e.g., Lambda function, SQS queue)
- **Module**: A reusable, self-contained package of Terraform configurations (analogous to Salesforce Unlocked Packages)
- **State**: A JSON file that tracks the current state of deployed infrastructure
- **Drift**: When actual infrastructure differs from what Terraform expects based on state and configuration
- **HCL**: HashiCorp Configuration Language, the syntax used in `.tf` files
- **Plan**: A preview of changes Terraform will make before applying them
- **Apply**: The action of executing planned changes to create/update/delete infrastructure

## Requirements

### Requirement 1: Core Concepts Understanding

**User Story:** As a Salesforce developer learning Terraform, I want to understand what Terraform is and how it compares to Salesforce deployment concepts, so that I can leverage my existing knowledge to learn faster.

#### Acceptance Criteria

1. WHEN the learner completes the core concepts module, THE Curriculum SHALL explain Terraform as "Metadata Deployment for AWS" with direct Salesforce analogies
2. WHEN explaining Terraform concepts, THE Curriculum SHALL map each concept to a Salesforce equivalent (e.g., `.tf` files = Metadata XML, `terraform apply` = `sf project deploy start`)
3. THE Curriculum SHALL explain the declarative nature of Terraform (describe desired state, not steps to achieve it)
4. WHEN introducing the three-way relationship, THE Curriculum SHALL clearly explain how `.tf` code, `.tfstate`, and actual AWS resources interact

### Requirement 2: File Structure Comprehension

**User Story:** As a Salesforce developer, I want to understand the purpose of each Terraform file type, so that I know where to make changes and what each file controls.

#### Acceptance Criteria

1. THE Curriculum SHALL explain `variables.tf` as analogous to Custom Metadata Type definitions (structure without values)
2. THE Curriculum SHALL explain `terraform.tfvars` as analogous to Custom Settings records (actual values, never committed to git)
3. THE Curriculum SHALL explain `main.tf` as the orchestrator that wires modules together (like `sfdx-project.json` referencing packages)
4. THE Curriculum SHALL explain `terraform.tfstate` as the deployment tracking file that must never be manually edited or deleted
5. WHEN explaining file relationships, THE Curriculum SHALL use the learner's existing project files as concrete examples

### Requirement 3: Essential Commands Mastery

**User Story:** As a Terraform beginner, I want to learn the core commands and their purposes, so that I can safely manage infrastructure.

#### Acceptance Criteria

1. THE Curriculum SHALL teach `terraform init` as the initialization command (analogous to installing SFDX plugins)
2. THE Curriculum SHALL teach `terraform plan` as a safe, read-only preview (analogous to `sf project deploy preview`)
3. THE Curriculum SHALL teach `terraform apply` as the deployment command (analogous to `sf project deploy start`)
4. THE Curriculum SHALL teach `terraform destroy` as the teardown command with appropriate warnings about permanence
5. THE Curriculum SHALL emphasize the "plan before apply" workflow as a critical safety practice
6. WHEN teaching commands, THE Curriculum SHALL include practical exercises using the learner's existing project

### Requirement 4: State Management Understanding

**User Story:** As a Terraform user, I want to understand how state works and why it matters, so that I can avoid common pitfalls that break deployments.

#### Acceptance Criteria

1. THE Curriculum SHALL explain state as Terraform's memory of what it has deployed
2. THE Curriculum SHALL explain the three-way comparison: state file vs. AWS reality vs. `.tf` code
3. THE Curriculum SHALL warn against manual state file editing with clear consequences
4. THE Curriculum SHALL warn against state file deletion with recovery guidance
5. WHEN explaining state, THE Curriculum SHALL demonstrate by showing the learner's actual `terraform.tfstate` structure
6. THE Curriculum SHALL explain state locking and how to handle lock errors

### Requirement 5: Drift Detection and Resolution

**User Story:** As a Terraform user, I want to understand what drift is and how to handle it, so that I can maintain consistency between code and infrastructure.

#### Acceptance Criteria

1. THE Curriculum SHALL define drift as the difference between Terraform's expected state and actual AWS resources
2. THE Curriculum SHALL explain common causes of drift (manual AWS console changes, other tools, team members)
3. THE Curriculum SHALL teach `terraform refresh` and `terraform plan` for drift detection
4. THE Curriculum SHALL teach two resolution strategies: override (apply) vs. accept (update `.tf` files)
5. THE Curriculum SHALL explain `lifecycle { ignore_changes }` for intentional drift allowance
6. WHEN teaching drift, THE Curriculum SHALL provide a practical exercise using the learner's project

### Requirement 6: Variables and Configuration

**User Story:** As a Terraform user, I want to understand how variables work, so that I can configure infrastructure without hardcoding values.

#### Acceptance Criteria

1. THE Curriculum SHALL explain variable declaration syntax with types (string, number, bool, list, map)
2. THE Curriculum SHALL explain variable precedence (defaults, tfvars, environment variables, CLI flags)
3. THE Curriculum SHALL explain the `sensitive = true` attribute for secrets
4. THE Curriculum SHALL compare variables to Salesforce Custom Settings and Custom Metadata Types
5. WHEN teaching variables, THE Curriculum SHALL use examples from the learner's `variables.tf` file
6. THE Curriculum SHALL explain string interpolation syntax (`${var.name}`)

### Requirement 7: Modules Understanding

**User Story:** As a Terraform user, I want to understand how modules work, so that I can organize code and reuse configurations.

#### Acceptance Criteria

1. THE Curriculum SHALL explain modules as reusable infrastructure packages (analogous to Unlocked Packages)
2. THE Curriculum SHALL explain module structure: inputs (variables), resources, and outputs
3. THE Curriculum SHALL explain how parent configurations call modules and pass variables
4. THE Curriculum SHALL explain how to use module outputs in other modules or root configuration
5. WHEN teaching modules, THE Curriculum SHALL walk through the learner's existing modules (bedrock_agent, lambda, sqs, secrets)
6. THE Curriculum SHALL explain the difference between local modules and registry modules

### Requirement 8: Practical Exercises

**User Story:** As a hands-on learner, I want practical exercises using my existing project, so that I can apply concepts immediately and build confidence.

#### Acceptance Criteria

1. THE Curriculum SHALL include an exercise to run `terraform plan` and interpret the output
2. THE Curriculum SHALL include an exercise to make a safe change (e.g., update a tag) and apply it
3. THE Curriculum SHALL include an exercise to intentionally create drift and resolve it
4. THE Curriculum SHALL include an exercise to add a new variable and use it
5. THE Curriculum SHALL include an exercise to trace a value through modules (input → resource → output)
6. WHEN providing exercises, THE Curriculum SHALL use the learner's actual project files and resources
7. THE Curriculum SHALL provide rollback instructions for each exercise

### Requirement 9: Safety and Best Practices

**User Story:** As a Terraform beginner, I want to learn safety practices and common pitfalls, so that I can avoid costly mistakes.

#### Acceptance Criteria

1. THE Curriculum SHALL emphasize never committing `terraform.tfvars` or `.tfstate` to git
2. THE Curriculum SHALL teach the importance of always running `plan` before `apply`
3. THE Curriculum SHALL explain idempotency (running apply twice produces same result)
4. THE Curriculum SHALL warn about `terraform destroy` permanence (no recycle bin)
5. THE Curriculum SHALL explain how to recover from common errors (state lock, resource already exists)
6. THE Curriculum SHALL provide a pre-flight checklist for safe Terraform operations
