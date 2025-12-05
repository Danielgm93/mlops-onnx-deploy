variable "aws_region" {
  description = "AWS region where resources will be created"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "Your AWS Account ID"
  type        = string
}

variable "project_name" {
  description = "Prefix for naming AWS resources"
  type        = string
  default     = "mlops-daniel"
}

variable "container_cpu" {
  description = "Fargate task CPU units"
  type        = string
  default     = "256"
}

variable "container_memory" {
  description = "Fargate task memory in MiB"
  type        = string
  default     = "512"
}

variable "desired_count_dev" {
  description = "Number of tasks for dev service"
  type        = number
  default     = 1
}

variable "desired_count_prod" {
  description = "Number of tasks for prod service"
  type        = number
  default     = 1
}
