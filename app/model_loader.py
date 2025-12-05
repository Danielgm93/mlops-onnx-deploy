import os
from functools import lru_cache
from typing import Optional

import boto3
import onnxruntime as ort


MODEL_S3_BUCKET_ENV = "MODEL_S3_BUCKET"
MODEL_S3_KEY_ENV = "MODEL_S3_KEY"
LOCAL_MODEL_PATH_ENV = "LOCAL_MODEL_PATH"
AWS_REGION_ENV = "AWS_REGION"


def get_local_model_path() -> str:
    """
    Ruta local donde se almacenará el modelo ONNX dentro del contenedor
    o durante los tests.
    """
    return os.getenv(LOCAL_MODEL_PATH_ENV, "/models/model.onnx")


def get_s3_client():
    """
    Crea un cliente S3 usando credenciales/region de entorno.
    """
    region = os.getenv(AWS_REGION_ENV)
    if region:
        return boto3.client("s3", region_name=region)
    return boto3.client("s3")


def download_model_from_s3(
    bucket: Optional[str] = None,
    key: Optional[str] = None,
    local_path: Optional[str] = None,
) -> str:
    """
    Descarga el modelo ONNX desde S3 a local_path.
    Los parámetros se pueden tomar desde variables de entorno.
    """
    bucket = bucket or os.getenv(MODEL_S3_BUCKET_ENV)
    key = key or os.getenv(MODEL_S3_KEY_ENV)
    local_path = local_path or get_local_model_path()

    if not bucket or not key:
        raise ValueError(
            "MODEL_S3_BUCKET y MODEL_S3_KEY deben estar definidos para descargar el modelo."
        )

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3 = get_s3_client()
    s3.download_file(bucket, key, local_path)
    return local_path


def ensure_model_downloaded() -> str:
    """
    Si el modelo no existe localmente, intenta descargarlo desde S3.
    """
    local_path = get_local_model_path()
    if not os.path.exists(local_path):
        download_model_from_s3(local_path=local_path)
    return local_path


def create_session_from_path(model_path: str) -> ort.InferenceSession:
    """
    Crea una sesión onnxruntime dado un path local al modelo ONNX.
    """
    # Providers por defecto; se puede ajustar para GPU si existe
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    return session


@lru_cache(maxsize=1)
def get_onnx_session() -> ort.InferenceSession:
    """
    Devuelve una sesión onnxruntime singleton, descargando el modelo si hace falta.
    Usada por la app FastAPI.
    """
    model_path = ensure_model_downloaded()
    return create_session_from_path(model_path)
