#!/usr/bin/env bash
set -euo pipefail

AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-""}

if [[ -z "${AWS_ACCOUNT_ID}" ]]; then
  echo "Set AWS_ACCOUNT_ID env var first."
  exit 1
fi

REPO_NAME=${ECR_REPOSITORY_NAME:-"mlops-onnx-api"}

echo "Creating ECR repository ${REPO_NAME} in region ${AWS_REGION}..."

aws ecr create-repository \
  --repository-name "${REPO_NAME}" \
  --image-scanning-configuration scanOnPush=true \
  --region "${AWS_REGION}" || true

echo "Repository ARN:"
aws ecr describe-repositories \
  --repository-names "${REPO_NAME}" \
  --region "${AWS_REGION}" \
  --query 'repositories[0].repositoryArn' \
  --output text
