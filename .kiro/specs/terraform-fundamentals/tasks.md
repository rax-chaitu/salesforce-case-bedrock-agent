# Implementation Plan: Terraform Fundamentals Learning Curriculum

## Overview

This plan creates a comprehensive Terraform learning curriculum document for Salesforce developers. The deliverable is a single markdown file (`docs/TERRAFORM_FUNDAMENTALS_CURRICULUM.md`) containing all 9 learning modules with Salesforce analogies, practical exercises, and safety guidance.

Since this is a documentation spec, all tasks involve writing markdown content rather than code implementation.

## Tasks

- [ ] 1. Create curriculum document structure and introduction
  - Create `docs/TERRAFORM_FUNDAMENTALS_CURRICULUM.md` with document skeleton
  - Write introduction explaining the curriculum's purpose and target audience
  - Add "How to Use This Guide" section with prerequisites
  - Include table of contents linking to all 9 modules
  - _Requirements: 1.1_

- [ ] 2. Write Module 1: The Mental Model
  - [ ] 2.1 Write the "What is Terraform" section
    - Include "Metadata Deployment for AWS" one-sentence explanation
    - Explain declarative vs imperative approach with SF comparison
    - _Requirements: 1.1, 1.3_
  
  - [ ] 2.2 Create the Salesforce-to-Terraform Rosetta Stone table
    - Map all core concepts: .tf files, tfvars, tfstate, modules, commands
    - Include at least 12 concept mappings
    - _Requirements: 1.2_

- [ ] 3. Write Module 2: The Three-Way Relationship
  - [ ] 3.1 Create the three-pillar diagram and explanation
    - Diagram showing .tf code ↔ .tfstate ↔ AWS Reality
    - Explain what happens during `terraform plan`
    - Use Salesforce deployment analogy (local metadata vs org)
    - _Requirements: 1.4, 4.2_

- [ ] 4. Write Module 3: File Anatomy
  - [ ] 4.1 Write variables.tf deep dive
    - Explain as Custom Metadata Type definition analogy
    - Show examples from project's `terraform/variables.tf`
    - Cover type, default, description, sensitive attributes
    - _Requirements: 2.1, 6.1, 6.3_
  
  - [ ] 4.2 Write terraform.tfvars explanation
    - Explain as Custom Settings records analogy
    - Show structure from `terraform/terraform.tfvars.example`
    - Emphasize NEVER commit to git warning
    - _Requirements: 2.2, 9.1_
  
  - [ ] 4.3 Write main.tf walkthrough
    - Explain as orchestrator/Package.xml analogy
    - Walk through project's `terraform/main.tf` structure
    - Show how modules are called and wired together
    - _Requirements: 2.3, 2.5_
  
  - [ ] 4.4 Write terraform.tfstate explanation
    - Explain state file purpose and structure
    - Show JSON structure example
    - Include strong warnings about manual editing/deletion
    - _Requirements: 2.4, 4.1, 4.3, 4.4_

- [ ] 5. Write Module 4: Command Mastery
  - [ ] 5.1 Create command reference table
    - Cover init, validate, plan, apply, destroy, output, fmt
    - Include safety level for each command
    - Map each to Salesforce CLI equivalent
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 5.2 Write the safety workflow section
    - Emphasize "plan before apply" as golden rule
    - Include the safe workflow bash example
    - Explain idempotency concept
    - _Requirements: 3.5, 9.2, 9.3_

- [ ] 6. Write Module 5: State Deep Dive
  - [ ] 6.1 Write "Why State Exists" section
    - Explain state as Terraform's memory
    - Cover tracking, dependencies, performance benefits
    - _Requirements: 4.1_
  
  - [ ] 6.2 Write state file anatomy section
    - Show JSON structure with annotations
    - Explain resource mappings
    - Reference project's actual state structure
    - _Requirements: 4.5_
  
  - [ ] 6.3 Write state locking and recovery section
    - Explain state locking mechanism
    - Cover `terraform force-unlock` with warnings
    - Include recovery procedures for common issues
    - _Requirements: 4.6, 9.5_

- [ ] 7. Write Module 6: Drift Management
  - [ ] 7.1 Write drift definition and causes section
    - Define drift clearly
    - List common causes (console changes, other tools, team members)
    - _Requirements: 5.1, 5.2_
  
  - [ ] 7.2 Write drift detection section
    - Cover `terraform refresh` and `terraform plan`
    - Show how to interpret drift in plan output
    - _Requirements: 5.3_
  
  - [ ] 7.3 Write drift resolution strategies section
    - Explain Option A: Override (apply)
    - Explain Option B: Accept (update .tf files)
    - Include `lifecycle { ignore_changes }` explanation
    - _Requirements: 5.4, 5.5_

- [ ] 8. Write Module 7: Variables & Configuration
  - [ ] 8.1 Write variable declaration section
    - Cover all types: string, number, bool, list, map
    - Show examples from project's variables.tf
    - _Requirements: 6.1, 6.5_
  
  - [ ] 8.2 Write variable precedence section
    - Explain order: defaults → tfvars → env → CLI
    - Show practical examples
    - _Requirements: 6.2_
  
  - [ ] 8.3 Write string interpolation and locals section
    - Explain `${var.name}` syntax
    - Cover local values as computed variables
    - Compare to Salesforce formula fields
    - _Requirements: 6.6, 6.4_

- [ ] 9. Write Module 8: Modules
  - [ ] 9.1 Write module concept explanation
    - Explain as Unlocked Packages analogy
    - Cover when to create modules
    - _Requirements: 7.1_
  
  - [ ] 9.2 Write module anatomy section
    - Explain inputs (variables), resources, outputs structure
    - Use project's `modules/sqs/main.tf` as example
    - _Requirements: 7.2_
  
  - [ ] 9.3 Write module usage section
    - Show how to call modules from main.tf
    - Explain passing variables and using outputs
    - Walk through project's module connections
    - _Requirements: 7.3, 7.4, 7.5_
  
  - [ ] 9.4 Write local vs registry modules section
    - Explain `source = "./modules/..."` vs registry
    - Cover versioning considerations
    - _Requirements: 7.6_

- [ ] 10. Write Module 9: Practical Exercises
  - [ ] 10.1 Write Exercise 1: Plan Interpretation
    - Step-by-step instructions to run `terraform plan`
    - Guide on reading and understanding output
    - Include rollback: N/A (read-only)
    - _Requirements: 8.1_
  
  - [ ] 10.2 Write Exercise 2: Safe Change
    - Instructions to add a tag to a resource
    - Apply and verify in AWS console
    - Include rollback: remove tag, apply again
    - _Requirements: 8.2, 8.7_
  
  - [ ] 10.3 Write Exercise 3: Create and Resolve Drift
    - Instructions to change something in AWS console
    - Detect with plan, resolve with both strategies
    - Include rollback: apply to restore
    - _Requirements: 8.3, 5.6, 8.7_
  
  - [ ] 10.4 Write Exercise 4: Add a Variable
    - Instructions to add new variable to variables.tf
    - Use it in a resource, apply
    - Include rollback: remove variable, apply
    - _Requirements: 8.4, 8.7_
  
  - [ ] 10.5 Write Exercise 5: Trace Value Flow
    - Instructions to trace a value from tfvars → module → resource → output
    - Use project's `project_name` variable as example
    - Include rollback: N/A (read-only)
    - _Requirements: 8.5, 8.6_

- [ ] 11. Write Safety and Reference sections
  - [ ] 11.1 Write pre-flight checklist
    - Checklist before running any Terraform command
    - Include AWS auth verification, plan review, backup reminders
    - _Requirements: 9.6_
  
  - [ ] 11.2 Write troubleshooting guide
    - Cover common errors: state lock, resource exists, credentials
    - Include recovery commands for each
    - _Requirements: 9.5_
  
  - [ ] 11.3 Write quick reference card
    - One-page command summary
    - Include most common flags
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [ ] 11.4 Add destroy permanence warning section
    - Emphasize no recycle bin
    - Recommend sandbox/test accounts for learning
    - _Requirements: 9.4_

- [ ] 12. Checkpoint - Review curriculum completeness
  - Verify all 9 modules are complete
  - Run through verification checklist from design document
  - Ensure all Salesforce analogies are present
  - Ensure all project file references are accurate
  - Ask the user if questions arise

- [ ] 13. Final review and polish
  - [ ] 13.1 Add table of contents with anchor links
    - Link to all major sections
    - Ensure navigation is easy
  
  - [ ] 13.2 Verify all code snippets are syntax-valid
    - Check HCL syntax in examples
    - Check bash command syntax
  
  - [ ] 13.3 Add version and last-updated information
    - Include Terraform version tested against
    - Add date for future reference

## Notes

- This is a documentation spec - all tasks create markdown content, not executable code
- Each module should be self-contained but reference other modules where appropriate
- Exercises should be safe to run against the existing project without causing damage
- All examples should use the learner's actual project files for relevance
- The curriculum builds progressively - earlier modules are prerequisites for later ones
