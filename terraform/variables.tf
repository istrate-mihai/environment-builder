variable "aws_region" {
  description = "AWS region for the server"
  type        = string
  default     = "eu-central-1"
}

variable "project_name" {
  description = "Prefix used for resource names"
  type        = string
  default     = "env-builder"
}

variable "instance_type" {
  description = "EC2 size; t3.small is the minimum that runs MySQL + Docker comfortably"
  type        = string
  default     = "t3.small"
}

variable "public_key_path" {
  description = "Path to the SSH public key uploaded as the EC2 key pair"
  type        = string
  default     = "~/.ssh/env-builder.pub"
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into the server, e.g. 1.2.3.4/32 (your IP)"
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_ssh_cidr, 0))
    error_message = "allowed_ssh_cidr must be a valid CIDR, e.g. 1.2.3.4/32."
  }
}
