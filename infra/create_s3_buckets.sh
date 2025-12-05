#!/usr/bin/env bash
set -euo pipefail

# Ejemplo de creación de buckets y rutas base.
# Ajusta la región y nombres según tu cuenta.

AWS_REGION=${AWS_REGION:-"us-east-1"}

MODEL_BUCKET="mlops-model-bucket"
LOGS_BUCKET="mlops-logs-bucket"

echo "Creating S3 buckets in region ${AWS_REGION}..."

aws s3api create-bucket \
  --bucket "${MODEL_BUCKET}" \
  --region "${AWS_REGION}" \
  --create-bucket-configuration LocationConstraint="${AWS_REGION}" || true

aws s3api create-bucket \
  --bucket "${LOGS_BUCKET}" \
  --region "${AWS_REGION}" \
  --create-bucket-configuration LocationConstraint="${AWS_REGION}" || true

echo "Buckets created (or already exist):"
echo "  s3://${MODEL_BUCKET}"
echo "  s3://${LOGS_BUCKET}"

echo "You should upload:"
echo "  - model.onnx to s3://${MODEL_BUCKET}/models/current/model.onnx"
echo "  - test_data.json to s3://${MODEL_BUCKET}/test-data/test_data.json"
echo "Logs will be written to:"
echo "  - s3://${LOGS_BUCKET}/predictions_dev.txt"
echo "  - s3://${LOGS_BUCKET}/predictions_prod.txt"
