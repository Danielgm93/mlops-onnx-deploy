import os

from app.model_loader import create_session_from_path, get_local_model_path
from app.predictor import predict_single


def test_model_responds_to_defined_input():
    """
    Verifica que el modelo ONNX responde correctamente
    a una entrada de prueba definida (sin error y con formato esperado).

    Requisitos:
    - El pipeline (o el usuario) debe haber descargado el modelo a LOCAL_MODEL_PATH.
    """
    model_path = get_local_model_path()
    assert os.path.exists(
        model_path
    ), f"Model file not found at {model_path}. Did you download it from S3?"

    session = create_session_from_path(model_path)

    # Entrada sintética razonable: vector de 4 features tipo Iris.
    test_features = [5.1, 3.5, 1.4, 0.2]

    pred = predict_single(session, test_features)

    # Simplemente verificamos que sea un entero (clase).
    assert isinstance(pred, int)
