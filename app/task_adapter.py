import os
from typing import Any, Dict

import onnxruntime as ort

from .ner_adapter import predict_text_ner, ner_f1_from_file


MODEL_TASK_ENV = "MODEL_TASK"


def get_model_task() -> str:
    """
    Devuelve la tarea actual del modelo (p.ej. 'ner', 'tabular', etc.).
    Por ahora solo soportamos 'ner'.
    """
    return os.getenv(MODEL_TASK_ENV, "ner").lower()


def predict_request(session: ort.InferenceSession, payload: Dict[str, Any]):
    """
    Punto único para hacer inferencia desde la API o tests.
    Interpreta el payload según MODEL_TASK.
    """
    task = get_model_task()

    if task == "ner":
        text = payload.get("text")
        if not isinstance(text, str):
            raise ValueError("Para MODEL_TASK=ner, el payload debe incluir 'text' (str).")
        return predict_text_ner(session, text)

    raise ValueError(f"Tarea no soportada: {task}")


def compute_metric(session: ort.InferenceSession, test_data_path: str) -> float:
    """
    Punto único para calcular la métrica de regresión/prueba del modelo.
    """
    task = get_model_task()

    if task == "ner":
        return ner_f1_from_file(session, test_data_path)

    raise ValueError(f"Tarea no soportada: {task}")
