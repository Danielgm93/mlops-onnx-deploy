#!/usr/bin/env bash
set -euo pipefail

AWS_REGION=${AWS_REGION:-"us-east-1"}
CLUSTER_NAME=${CLUSTER_NAME:-"mlops-onnx-cluster"}
SERVICE_NAME_DEV=${SERVICE_NAME_DEV:-"mlops-onnx-api-dev"}
SERVICE_NAME_PROD=${SERVICE_NAME_PROD:-"mlops-onnx-api-prod"}
ECR_REPOSITORY_NAME=${ECR_REPOSITORY_NAME:-"mlops-onnx-api"}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-""}

if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
  echo "Set AWS_ACCOUNT_ID env var first."
  exit 1
fi

IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY_NAME}:latest"

echo "Creating ECS cluster ${CLUSTER_NAME}..."
aws ecs create-cluster --cluster-name "${CLUSTER_NAME}" --region "${AWS_REGION}" || true

echo "You must create:"
echo "  - Fargate task execution role (ecsTaskExecutionRole)"
echo "  - Security groups, subnets and ALB (outside this script)."
echo "Then define a Fargate task definition that uses IMAGE_URI=${IMAGE_URI}"
echo "with container env vars:"
echo "   ENVIRONMENT=dev/prod"
echo "   MODEL_S3_BUCKET, MODEL_S3_KEY, PREDICTIONS_S3_BUCKET, PREDICTIONS_S3_KEY, etc."
echo
echo "Finally, create two ECS services (one for dev, one for prod) pointing to the same"
echo "task definition family but different environment variables and target groups."
echo
echo "Example (very simplified, without networking args):"
echo "aws ecs create-service --cluster ${CLUSTER_NAME} --service-name ${SERVICE_NAME_DEV} \\"
echo "  --task-definition mlops-onnx-task \\"
echo "  --desired-count 1 --launch-type FARGATE ..."
echo
echo "aws ecs create-service --cluster ${CLUSTER_NAME} --service-name ${SERVICE_NAME_PROD} \\"
echo "  --task-definition mlops-onnx-task \\"
echo "  --desired-count 1 --launch-type FARGATE ..."
