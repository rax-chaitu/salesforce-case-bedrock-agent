################################################################################
# Lambda Layer Module - Rackspace Salesforce Auth
#
# Shared JWT auth layer reusable by any Lambda in this account.
# Lambdas import: from rackspace_sf_auth import SalesforceAuthClient
################################################################################

variable "project_name" {
  type = string
}

locals {
  layer_src = "${path.module}/../../../lambda/layers/rackspace_sf_auth"
}

resource "null_resource" "build_layer" {
  triggers = {
    auth_code    = filemd5("${local.layer_src}/rackspace_sf_auth/auth.py")
    init_code    = filemd5("${local.layer_src}/rackspace_sf_auth/__init__.py")
    requirements = filemd5("${local.layer_src}/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ${local.layer_src}
      rm -rf python
      mkdir -p python/rackspace_sf_auth
      pip3 install -r requirements.txt -t python/ \
        --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all:
      cp rackspace_sf_auth/__init__.py python/rackspace_sf_auth/
      cp rackspace_sf_auth/auth.py python/rackspace_sf_auth/
    EOT
  }
}

data "archive_file" "layer_zip" {
  depends_on  = [null_resource.build_layer]
  type        = "zip"
  source_dir  = "${local.layer_src}"
  output_path = "${path.module}/rackspace_sf_auth_layer.zip"
  excludes    = ["__pycache__", "*.pyc", "requirements.txt", "rackspace_sf_auth"]
}

resource "aws_lambda_layer_version" "sf_auth" {
  filename            = data.archive_file.layer_zip.output_path
  source_code_hash    = data.archive_file.layer_zip.output_base64sha256
  layer_name          = "${var.project_name}-rackspace-sf-auth"
  compatible_runtimes = ["python3.11", "python3.12"]
  description         = "Rackspace Salesforce JWT auth - reusable across all agent Lambdas"
}

output "layer_arn" {
  value = aws_lambda_layer_version.sf_auth.arn
}
