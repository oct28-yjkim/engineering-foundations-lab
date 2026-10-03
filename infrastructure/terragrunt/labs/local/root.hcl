# Not a runnable unit. No hooks, run_cmd, remote backends, or credentials.
terraform_version_constraint  = "= 1.16.5"
terragrunt_version_constraint = "= 1.1.6"

inputs = {
  revision = 1
  components = {
    ingest = 1
    serve  = 2
  }
}
