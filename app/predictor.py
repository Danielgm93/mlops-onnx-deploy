from typing import List, Sequence

import numpy as np
import onnxruntime as ort


def predict_single(session: ort.InferenceSession, features: Sequence[float]) -> int:
    """
    Realiza una predicción para un solo ejemplo (lista de floats).

    Pensado para un modelo de clasificación tipo Iris con entrada [f1, f2, f3, f4].
    Output genérico:
    - Si la salida es 2D con >1 columna, se toma argmax (clasificación multiclase).
    - En otro caso, se redondea el valor y se castea a int.
    """
    input_name = session.get_inputs()[0].name
    x = np.array([features], dtype=np.float32)  # shape (1, n_features)
    outputs = session.run(None, {input_name: x})
    y = outputs[0]

    if y.ndim == 2 and y.shape[1] > 1:
        pred_class = int(np.argmax(y, axis=1)[0])
    else:
        # Binario o regresión; aquí se fuerza a entero.
        pred_class = int(round(float(y[0][0])))

    return pred_class


def predict_batch(session: ort.InferenceSession, batch_features: List[Sequence[float]]) -> List[int]:
    """
    Predicción para un batch de ejemplos.
    Devuelve una lista de enteros (clases).
    """
    input_name = session.get_inputs()[0].name
    x = np.array(batch_features, dtype=np.float32)  # shape (batch, n_features)
    outputs = session.run(None, {input_name: x})
    y = outputs[0]

    if y.ndim == 2 and y.shape[1] > 1:
        preds = np.argmax(y, axis=1).astype(int).tolist()
    else:
        preds = [int(round(float(v))) for v in y.reshape(-1)]
    return preds
