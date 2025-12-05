import os

from app.model_loader import create_session_from_path, get_local_model_path
from app.task_adapter import compute_metric


def test_metric_above_threshold():
    """
    Verifica que la métrica (F1 sobre entidades NER) calculada con datos de prueba
    no caiga por debajo de un umbral definido.

    Requisitos:
    - El pipeline debe haber descargado los datos de prueba a TEST_DATA_LOCAL_PATH.
    - El modelo debe estar disponible en LOCAL_MODEL_PATH.
    - La variable MIN_ACCEPTABLE_ACCURACY se usa como umbral de F1.
    """
    test_data_path = os.getenv("TEST_DATA_LOCAL_PATH", "tests_data/test_data.json")
    assert os.path.exists(
        test_data_path
    ), f"Test data not found at {test_data_path}. Did you download it from S3?"

    model_path = get_local_model_path()
    assert os.path.exists(
        model_path
    ), f"Model file not found at {model_path}. Did you download it from S3?"

    session = create_session_from_path(model_path)

    f1 = compute_metric(session, test_data_path)

    min_f1 = float(os.getenv("MIN_ACCEPTABLE_ACCURACY", "0.7"))
    assert (
        f1 >= min_f1
    ), f"Model F1 {f1:.3f} is below threshold {min_f1:.3f}"
