output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.app.dns_name
}

output "dev_url_example" {
  description = "Example dev URL (path-based routing)"
  value       = "http://${aws_lb.app.dns_name}/dev/predict"
}

output "prod_url_example" {
  description = "Example prod URL (path-based routing)"
  value       = "http://${aws_lb.app.dns_name}/prod/predict"
}

output "model_bucket_name" {
  value = aws_s3_bucket.model.bucket
}

output "logs_bucket_name" {
  value = aws_s3_bucket.logs.bucket
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_dev_name" {
  value = aws_ecs_service.dev.name
}

output "ecs_service_prod_name" {
  value = aws_ecs_service.prod.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.this.repository_url
}
