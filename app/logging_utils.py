import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


PREDICTIONS_S3_BUCKET_ENV = "PREDICTIONS_S3_BUCKET"
PREDICTIONS_S3_KEY_ENV = "PREDICTIONS_S3_KEY"
AWS_REGION_ENV = "AWS_REGION"


def _get_s3_client():
    region = os.getenv(AWS_REGION_ENV)
    if region:
        return boto3.client("s3", region_name=region)
    return boto3.client("s3")


def append_prediction_log(
    request_payload: Dict[str, Any],
    prediction: Any,
    environment: Optional[str] = None,
) -> None:
    """
    Añade una línea a un archivo de texto en S3 con la predicción realizada.

    La ubicación se define por:
      - PREDICTIONS_S3_BUCKET
      - PREDICTIONS_S3_KEY  (p.e. 'predictions_dev.txt' o 'predictions_prod.txt')

    Formato de línea: JSON por línea (JSONL).
    """
    bucket = os.getenv(PREDICTIONS_S3_BUCKET_ENV)
    key = os.getenv(PREDICTIONS_S3_KEY_ENV)

    if not bucket or not key:
        # Para no reventar la API si falta configuración, se hace log local.
        print(
            "[WARN] PREDICTIONS_S3_BUCKET/KEY no definidos; "
            f"no se subirá el log a S3. Payload={request_payload}, prediction={prediction}"
        )
        return

    s3 = _get_s3_client()

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "environment": environment,
        "request": request_payload,
        "prediction": prediction,
    }
    line = json.dumps(entry) + "\n"

    # Estrategia simple: leer el contenido actual y re-escribir con el nuevo final.
    # No es óptimo para alta concurrencia, pero suficiente para este proyecto.
    existing = ""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        existing = obj["Body"].read().decode("utf-8")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code not in ("NoSuchKey", "NoSuchBucket"):
            raise

    new_body = (existing + line).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=new_body)
