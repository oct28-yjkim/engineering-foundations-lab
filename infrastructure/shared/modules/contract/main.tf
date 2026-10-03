# LOCAL TEACHING FIXTURE: built-in terraform_data only. No provider downloads,
# provisioners, external data sources, cloud resources, or remote backend here.
terraform {
  required_version = "= 1.16.5"
}

variable "unit_name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,31}$", var.unit_name))
    error_message = "Use a synthetic unit name: 3..32 lowercase letters, digits, or hyphens."
  }
}

variable "upstream_unit" {
  type    = string
  default = "none"
}

variable "revision" {
  type    = number
  default = 1
  validation {
    condition     = var.revision >= 1 && floor(var.revision) == var.revision
    error_message = "revision must be a positive integer."
  }
}

variable "components" {
  type = map(number)
  default = {
    ingest = 1
    serve  = 2
  }
  validation {
    condition = length(var.components) > 0 && alltrue([
      for key, capacity in var.components :
      can(regex("^[a-z][a-z0-9-]*$", key)) && capacity >= 1 && floor(capacity) == capacity
    ])
    error_message = "components needs nonempty stable keys and positive integer capacities."
  }
}

resource "terraform_data" "unit" {
  input = {
    unit_name     = var.unit_name
    upstream_unit = var.upstream_unit
    revision      = var.revision
  }
  triggers_replace = var.revision
}

resource "terraform_data" "component" {
  for_each = var.components
  input = {
    unit_name = terraform_data.unit.output.unit_name
    key       = each.key
    capacity  = each.value
  }
}

output "unit_name" {
  value = terraform_data.unit.output.unit_name
}

output "unit_id" {
  value = terraform_data.unit.id
}

output "manifest" {
  value = {
    unit       = terraform_data.unit.output
    components = { for key, item in terraform_data.component : key => item.output }
  }
}
