terraform {
  required_version = "= 1.16.5"
  backend "local" {}
}

variable "unit_name" {
  type    = string
  default = "terraform-lab"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,31}$", var.unit_name))
    error_message = "unit_name must be a synthetic lowercase name of 3..32 characters."
  }
}

variable "revision" {
  type    = number
  default = 1
}

module "contract" {
  source    = "../../../shared/modules/contract"
  unit_name = var.unit_name
  revision  = var.revision
}

output "manifest" {
  value = module.contract.manifest
}

output "unit_id" {
  value = module.contract.unit_id
}
