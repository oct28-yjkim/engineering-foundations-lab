include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_terragrunt_dir()}/../../../../../shared/modules/contract"
}

remote_state {
  backend = "local"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    path = "${get_terragrunt_dir()}/terraform.tfstate"
  }
}

dependency "foundation" {
  config_path = "../foundation"
  mock_outputs = {
    unit_name = "mock-foundation"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  unit_name     = "application"
  upstream_unit = dependency.foundation.outputs.unit_name
}
