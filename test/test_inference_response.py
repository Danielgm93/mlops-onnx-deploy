import os

from app.model_loader import create_session_from_path, get_local_model_path
from app.task_adapter import predict_request


def test_model_responds_to_defined_input():
    """
    Verifica que el modelo ONNX responde correctamente
    a una entrada de texto definida (sin error y con formato esperado).

    Requisitos:
    - El pipeline (o el usuario) debe haber descargado el modelo a LOCAL_MODEL_PATH.
    """
    model_path = get_local_model_path()
    assert os.path.exists(
        model_path
    ), f"Model file not found at {model_path}. Did you download it from S3?"

    session = create_session_from_path(model_path)

    # Texto sintético razonable para NER
    payload = {"text": "Andres vive en Cali"}

    result = predict_request(session, payload)

    # Verificamos formato básico
    assert isinstance(result, list)
    if result:
        first = result[0]
        assert isinstance(first, dict)
        for key in ("text", "label", "start", "end"):
            assert key in first
