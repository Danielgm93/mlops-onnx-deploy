terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  # Nombres derivados del proyecto
  model_bucket_name = "${var.project_name}-model-bucket"
  logs_bucket_name  = "${var.project_name}-logs-bucket"

  ecr_repo_name     = "${var.project_name}-onnx-api"
  ecs_cluster_name  = "${var.project_name}-onnx-cluster"

  ecs_service_dev_name  = "${var.project_name}-onnx-dev"
  ecs_service_prod_name = "${var.project_name}-onnx-prod"

  # Rutas en S3
  model_s3_key     = "models/current/model.onnx"
  test_data_s3_key = "test-data/test_data.json"

  # Imagen inicial (bootstrap). Luego el CI/CD actualizará el tag.
  initial_image_uri = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.ecr_repo_name}:bootstrap"

  # Nombre del contenedor ECS
  container_name = "mlops-onnx-container"
}

# =========================================
# Red básica (VPC, subnets públicas, IGW)
# =========================================

resource "aws_vpc" "this" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = {
    Name = "${var.project_name}-public-a"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = "10.0.2.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}b"

  tags = {
    Name = "${var.project_name}-public-b"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# =========================================
# Security Groups
# =========================================

# SG para el ALB (HTTP 80 desde Internet)
resource "aws_security_group" "alb_sg" {
  name        = "${var.project_name}-alb-sg"
  description = "ALB security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTP from the world"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

# SG para tareas ECS (solo desde el ALB en 8000)
resource "aws_security_group" "ecs_sg" {
  name        = "${var.project_name}-ecs-sg"
  description = "ECS tasks security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    description      = "From ALB on 8000"
    from_port        = 8000
    to_port          = 8000
    protocol         = "tcp"
    security_groups  = [aws_security_group.alb_sg.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ecs-sg"
  }
}

# =========================================
# S3 buckets (modelo + logs)
# =========================================

resource "aws_s3_bucket" "model" {
  bucket = local.model_bucket_name

  tags = {
    Name = local.model_bucket_name
  }
}

resource "aws_s3_bucket" "logs" {
  bucket = local.logs_bucket_name

  tags = {
    Name = local.logs_bucket_name
  }
}

# (Opcional) Versionado o encriptación se pueden agregar si hace falta.

# =========================================
# ECR repo
# =========================================

resource "aws_ecr_repository" "this" {
  name                 = local.ecr_repo_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = local.ecr_repo_name
  }
}

# =========================================
# ECS Cluster
# =========================================

resource "aws_ecs_cluster" "this" {
  name = local.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name = local.ecs_cluster_name
  }
}

# =========================================
# IAM roles para ECS Fargate
# =========================================

data "aws_iam_policy_document" "ecs_task_execution_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${var.project_name}-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Role de tarea (para S3, CloudWatch Logs, etc.)
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_role" {
  name               = "${var.project_name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

# Permisos S3 básicos (ajusta si quieres algo más fino)
data "aws_iam_policy_document" "ecs_task_role_policy_doc" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject"
    ]

    resources = [
      "${aws_s3_bucket.model.arn}/*",
      "${aws_s3_bucket.logs.arn}/*"
    ]
  }
}

resource "aws_iam_role_policy" "ecs_task_role_policy" {
  name   = "${var.project_name}-ecs-task-s3-policy"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_role_policy_doc.json
}

# =========================================
# CloudWatch Log Group
# =========================================

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}-onnx"
  retention_in_days = 7
}

# =========================================
# Load Balancer + Target Groups + Listener
# =========================================

resource "aws_lb" "app" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]

  enable_deletion_protection = false

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_target_group" "dev" {
  name        = "${var.project_name}-tg-dev"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"

  health_check {
    path                = "/health"
    port                = "8000"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    unhealthy_threshold = 2
    healthy_threshold   = 2
  }
}

resource "aws_lb_target_group" "prod" {
  name        = "${var.project_name}-tg-prod"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"

  health_check {
    path                = "/health"
    port                = "8000"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    unhealthy_threshold = 2
    healthy_threshold   = 2
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.dev.arn
  }
}

# Regla para /dev/*
resource "aws_lb_listener_rule" "dev_path" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.dev.arn
  }

  condition {
    path_pattern {
      values = ["/dev/*"]
    }
  }
}

# Regla para /prod/*
resource "aws_lb_listener_rule" "prod_path" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.prod.arn
  }

  condition {
    path_pattern {
      values = ["/prod/*"]
    }
  }
}

# =========================================
# ECS Task Definitions (dev y prod)
# =========================================

# Definición base del contenedor (compartida) y solo cambiamos ENVIRONMENT y PREDICTIONS_S3_KEY

locals {
  common_env_vars = [
    {
      name  = "MODEL_S3_BUCKET"
      value = aws_s3_bucket.model.bucket
    },
    {
      name  = "MODEL_S3_KEY"
      value = local.model_s3_key
    },
    {
      name  = "PREDICTIONS_S3_BUCKET"
      value = aws_s3_bucket.logs.bucket
    },
    {
      name  = "AWS_REGION"
      value = var.aws_region
    },
    {
      name  = "LOCAL_MODEL_PATH"
      value = "/models/model.onnx"
    },
    {
      name  = "MIN_ACCEPTABLE_ACCURACY"
      value = "0.7"
    }
  ]
}

# Task definition DEV
resource "aws_ecs_task_definition" "dev" {
  family                   = "${var.project_name}-onnx-task-dev"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory

  execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn      = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = local.initial_image_uri
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = concat(
        local.common_env_vars,
        [
          {
            name  = "ENVIRONMENT"
            value = "dev"
          },
          {
            name  = "PREDICTIONS_S3_KEY"
            value = "predictions_dev.txt"
          }
        ]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.app.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs-dev"
        }
      }
    }
  ])

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}

# Task definition PROD
resource "aws_ecs_task_definition" "prod" {
  family                   = "${var.project_name}-onnx-task-prod"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory

  execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn      = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = local.container_name
      image     = local.initial_image_uri
      essential = true
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = concat(
        local.common_env_vars,
        [
          {
            name  = "ENVIRONMENT"
            value = "prod"
          },
          {
            name  = "PREDICTIONS_S3_KEY"
            value = "predictions_prod.txt"
          }
        ]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.app.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs-prod"
        }
      }
    }
  ])

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}

# =========================================
# ECS Services DEV y PROD
# =========================================

resource "aws_ecs_service" "dev" {
  name            = local.ecs_service_dev_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.dev.arn
  desired_count   = var.desired_count_dev
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups = [aws_security_group.ecs_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.dev.arn
    container_name   = local.container_name
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "prod" {
  name            = local.ecs_service_prod_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.prod.arn
  desired_count   = var.desired_count_prod
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups = [aws_security_group.ecs_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.prod.arn
    container_name   = local.container_name
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}
