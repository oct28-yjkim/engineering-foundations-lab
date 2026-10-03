# apply is intentional: only built-in terraform_data in an isolated test state.
# Do not copy these commands to modules with cloud providers or provisioners.
run "initial_contract" {
  command = apply
  assert {
    condition = output.manifest.unit.unit_name == "terraform-lab" && (
      output.manifest.unit.revision == 1 && output.manifest.unit.upstream_unit == "none"
    )
    error_message = "The independent unit oracle differs."
  }
  assert {
    condition = output.manifest.components == {
      ingest = { unit_name = "terraform-lab", key = "ingest", capacity = 1 }
      serve  = { unit_name = "terraform-lab", key = "serve", capacity = 2 }
    }
    error_message = "Component keys, capacities, and unit bindings must match exactly."
  }
  assert {
    condition     = length(output.unit_id) > 0
    error_message = "The built-in resource ID must exist after apply."
  }
}

run "unchanged_contract" {
  command = plan
  assert {
    condition     = output.unit_id == run.initial_contract.unit_id
    error_message = "The unchanged configuration must retain the resource identity."
  }
}

run "reject_invalid_name" {
  command = plan
  variables {
    unit_name = "INVALID NAME"
  }
  expect_failures = [var.unit_name]
}
