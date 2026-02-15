################################################################################
# Lambda Layer Module - Rackspace Salesforce Queries
#
# Shared query helpers reusable by any action group Lambda.
# Lambdas import: from rackspace_sf_queries import query_sf, search_by_keywords
# Requires rackspace_sf_auth layer for SF connection.
################################################################################

variable "project_name" {
  type = string
}

locals {
  layer_src = "${path.module}/../../../lambda/layers/rackspace_sf_queries"
}

resource "null_resource" "build_layer" {
  triggers = {
    queries_code = filemd5("${local.layer_src}/rackspace_sf_queries/queries.py")
    init_code    = filemd5("${local.layer_src}/rackspace_sf_queries/__init__.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ${local.layer_src}
      rm -rf python
      mkdir -p python/rackspace_sf_queries
      cp rackspace_sf_queries/__init__.py python/rackspace_sf_queries/
      cp rackspace_sf_queries/queries.py python/rackspace_sf_queries/
    EOT
  }
}

data "archive_file" "layer_zip" {
  depends_on  = [null_resource.build_layer]
  type        = "zip"
  source_dir  = "${local.layer_src}"
  output_path = "${path.module}/rackspace_sf_queries_layer.zip"
  excludes    = ["__pycache__", "*.pyc", "requirements.txt", "rackspace_sf_queries"]
}

resource "aws_lambda_layer_version" "sf_queries" {
  filename            = data.archive_file.layer_zip.output_path
  source_code_hash    = data.archive_file.layer_zip.output_base64sha256
  layer_name          = "rackspace-sf-queries"
  compatible_runtimes = ["python3.11", "python3.12"]
  description         = "Rackspace Salesforce query helpers - reusable across all action group Lambdas"
}

output "layer_arn" {
  value = aws_lambda_layer_version.sf_queries.arn
}
