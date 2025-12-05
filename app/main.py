import os
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model_loader import get_onnx_session
from .predictor import predict_single
from .logging_utils import append_prediction_log


class PredictRequest(BaseModel):
    """
    Request para /predict.

    Ejemplo de cuerpo:
    {
      "features": [5.1, 3.5, 1.4, 0.2]
    }
    """
    features: List[float]


class PredictResponse(BaseModel):
    prediction: int


app = FastAPI(title="MLOps ONNX Inference API")


@app.on_event("startup")
def startup_event():
    """
    Durante el arranque de la app se asegura que el modelo esté descargado
    y cargado en memoria.
    """
    try:
        # Esto inicializa la sesión singleton (descarga el modelo si hace falta).
        get_onnx_session()
    except Exception as e:
        # Si el modelo no puede cargarse, mejor fallar en startup.
        raise RuntimeError(f"Error al inicializar el modelo ONNX: {e}") from e


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest):
    """
    Endpoint principal de inferencia.
    """
    try:
        session = get_onnx_session()
        pred = predict_single(session, req.features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during inference: {e}")

    # Registrar la predicción en S3
    environment = os.getenv("ENVIRONMENT", "unknown")
    try:
        append_prediction_log(
            request_payload=req.dict(),
            prediction=pred,
            environment=environment,
        )
    except Exception as e:
        # No se cae la predicción por fallo de logging.
        print(f"[WARN] Error al escribir log de predicción en S3: {e}")

    return PredictResponse(prediction=pred)
