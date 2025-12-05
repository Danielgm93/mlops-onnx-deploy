import json
import os
from typing import List

from app.model_loader import create_session_from_path, get_local_model_path
from app.predictor import predict_batch


def _load_test_data(path: str):
    """
    Espera un JSON con forma:
    {
      "features": [[...], [...], ...],
      "labels": [0, 1, 2, ...]
    }
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["features"], data["labels"]


def _accuracy(y_true: List[int], y_pred: List[int]) -> float:
    assert len(y_true) == len(y_pred)
    correct = sum(int(a == b) for a, b in zip(y_true, y_pred))
    return correct / len(y_true)


def test_metric_above_threshold():
    """
    Verifica que la métrica (accuracy) calculada con datos de prueba
    no caiga por debajo de un umbral definido.

    Requisitos:
    - El pipeline debe haber descargado los datos de prueba a TEST_DATA_LOCAL_PATH.
    - El modelo debe estar disponible en LOCAL_MODEL_PATH.
    - La variable MIN_ACCEPTABLE_ACCURACY puede venir de entorno.
    """
    test_data_path = os.getenv("TEST_DATA_LOCAL_PATH", "tests_data/test_data.json")
    assert os.path.exists(
        test_data_path
    ), f"Test data not found at {test_data_path}. Did you download it from S3?"

    features, labels = _load_test_data(test_data_path)

    model_path = get_local_model_path()
    assert os.path.exists(
        model_path
    ), f"Model file not found at {model_path}. Did you download it from S3?"

    session = create_session_from_path(model_path)
    preds = predict_batch(session, features)

    acc = _accuracy(labels, preds)

    min_acc = float(os.getenv("MIN_ACCEPTABLE_ACCURACY", "0.7"))
    assert (
        acc >= min_acc
    ), f"Model accuracy {acc:.3f} is below threshold {min_acc:.3f}"
