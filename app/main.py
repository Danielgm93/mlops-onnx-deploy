import os
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model_loader import get_onnx_session
from .logging_utils import append_prediction_log
from .task_adapter import predict_request


class Entity(BaseModel):
    text: str
    label: str
    start: int
    end: int


class PredictRequest(BaseModel):
    """
    Ejemplo de cuerpo:
    {
      "text": "Andres vive en Cali"
    }
    """
    text: str


class PredictResponse(BaseModel):
    entities: List[Entity]


app = FastAPI(title="MLOps ONNX NER API")


@app.on_event("startup")
def startup_event():
    """
    Durante el arranque de la app se asegura que el modelo esté descargado
    y cargado en memoria.
    """
    try:
        get_onnx_session()
    except Exception as e:
        raise RuntimeError(f"Error al inicializar el modelo ONNX: {e}") from e


@app.get("/health")
@app.get("/dev/health")
@app.get("/prod/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
@app.post("/dev/predict", response_model=PredictResponse)
@app.post("/prod/predict", response_model=PredictResponse)
def predict_endpoint(req: PredictRequest):
    """
    Endpoint principal de inferencia NER sobre texto.
    """
    try:
        session = get_onnx_session()
        raw_entities = predict_request(session, req.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during inference: {e}")

    # Normalizamos a objetos Entity
    entities = [Entity(**ent) for ent in raw_entities]

    # Registrar la predicción en S3
    environment = os.getenv("ENVIRONMENT", "unknown")
    try:
        append_prediction_log(
            request_payload=req.dict(),
            prediction=[e.dict() for e in entities],
            environment=environment,
        )
    except Exception as e:
        # No se cae la predicción por fallo de logging.
        print(f"[WARN] Error al escribir log de predicción en S3: {e}")

    return PredictResponse(entities=entities)
