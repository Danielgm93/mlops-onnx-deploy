import os
from functools import lru_cache
from typing import Any, Dict, List, Tuple, Set

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer, AutoConfig


TOKENIZER_ID_ENV = "TOKENIZER_ID"
DEFAULT_TOKENIZER_ID = "dslim/bert-base-NER"


@lru_cache(maxsize=1)
def get_tokenizer():
    """
    Carga y cachea el tokenizer de Hugging Face.
    """
    tokenizer_id = os.getenv(TOKENIZER_ID_ENV, DEFAULT_TOKENIZER_ID)
    return AutoTokenizer.from_pretrained(tokenizer_id)


@lru_cache(maxsize=1)
def get_id2label() -> Dict[int, str]:
    """
    Obtiene el mapeo id->label desde la config del modelo de Hugging Face.
    Esto asume que el modelo ONNX comparte el mismo esquema de etiquetas.
    """
    tokenizer_id = os.getenv(TOKENIZER_ID_ENV, DEFAULT_TOKENIZER_ID)
    config = AutoConfig.from_pretrained(tokenizer_id)
    # id2label puede venir con keys str o int; normalizamos a int.
    return {int(k): v for k, v in config.id2label.items()}


def _prepare_inputs_for_session(
    session: ort.InferenceSession, encoded: Dict[str, Any]
) -> Dict[str, np.ndarray]:
    """
    Toma el dict devuelto por el tokenizer y filtra solo las claves
    que el modelo ONNX espera como entrada.
    """
    input_names = {inp.name for inp in session.get_inputs()}
    feeds = {}
    for key, value in encoded.items():
        if key in input_names:
            # value ya es np.ndarray si usamos return_tensors="np"
            feeds[key] = value
    return feeds


def predict_text_ner(session: ort.InferenceSession, text: str) -> List[Dict[str, Any]]:
    """
    Ejecuta el modelo NER sobre un texto y devuelve una lista de entidades:

    [
      {"text": "Andres", "label": "PER", "start": 0, "end": 6},
      {"text": "Cali", "label": "LOC", "start": 17, "end": 21},
      ...
    ]
    """
    tokenizer = get_tokenizer()
    id2label = get_id2label()

    encoded = tokenizer(
        text,
        return_offsets_mapping=True,
        truncation=True,
        max_length=128,
        return_tensors="np",
    )

    offsets = encoded["offset_mapping"][0]  # shape (seq_len, 2)
    input_ids = encoded["input_ids"][0]     # shape (seq_len,)
    tokens = tokenizer.convert_ids_to_tokens(input_ids.tolist())

    feeds = _prepare_inputs_for_session(session, encoded)
    if not feeds:
        raise ValueError("No se pudo mapear ninguna entrada del tokenizer al modelo ONNX.")

    outputs = session.run(None, feeds)
    # Para modelos de token classification estilo BERT NER, asumimos:
    # logits shape: (batch_size=1, seq_len, num_labels)
    logits = outputs[0]
    if logits.ndim != 3:
        raise ValueError(f"Se esperaba salida 3D (batch, seq_len, num_labels), se obtuvo {logits.shape}")

    pred_ids = np.argmax(logits, axis=-1)[0]  # (seq_len,)

    entities: List[Dict[str, Any]] = []

    # Recorremos tokens y offsets; cada token con label != "O" se considera entidad.
    for idx, (token, (start, end), label_id) in enumerate(
        zip(tokens, offsets, pred_ids)
    ):
        # offsets (0,0) suelen ser tokens especiales ([CLS], [SEP], etc.) → se ignoran
        if int(start) == 0 and int(end) == 0:
            continue

        label = id2label.get(int(label_id), f"LABEL_{int(label_id)}")
        if label == "O":
            continue

        # limpiamos prefijo B- / I- si existe
        label_clean = label.split("-", 1)[-1]

        start_idx = int(start)
        end_idx = int(end)
        span_text = text[start_idx:end_idx]

        entities.append(
            {
                "text": span_text,
                "label": label_clean,
                "start": start_idx,
                "end": end_idx,
            }
        )

    return entities


def _load_ner_test_data(path: str) -> Tuple[List[str], List[List[Dict[str, Any]]]]:
    """
    Espera un JSON con forma:

    {
      "sentences": [
        "Andres vive en Cali",
        "IBM está en Nueva York"
      ],
      "entities": [
        [
          {"text": "Andres", "label": "PER"},
          {"text": "Cali", "label": "LOC"}
        ],
        [
          {"text": "IBM", "label": "ORG"},
          {"text": "Nueva York", "label": "LOC"}
        ]
      ]
    }
    """
    import json

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sentences = data["sentences"]
    entities = data["entities"]
    return sentences, entities


def _to_span_set(entities: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    """
    Convierte una lista de entidades en un set de (label, text) para
    facilitar el cálculo de precision/recall a nivel de span.
    """
    s: Set[Tuple[str, str]] = set()
    for ent in entities:
        text = ent["text"]
        label = ent["label"]
        s.add((label, text))
    return s


def ner_f1_from_file(session: ort.InferenceSession, test_data_path: str) -> float:
    """
    Calcula una métrica F1 sencilla a nivel de spans (label, text) usando
    el archivo JSON de test descrito en _load_ner_test_data.
    """
    sentences, gold_entities_all = _load_ner_test_data(test_data_path)

    total_gold = 0
    total_pred = 0
    total_correct = 0

    for sent, gold_entities in zip(sentences, gold_entities_all):
        gold_set = _to_span_set(gold_entities)
        pred_entities = predict_text_ner(session, sent)
        pred_set = _to_span_set(pred_entities)

        total_gold += len(gold_set)
        total_pred += len(pred_set)
        total_correct += len(gold_set & pred_set)

    if total_pred == 0 and total_gold == 0:
        # no hay entidades → consideramos F1=1 por conveniencia
        return 1.0

    if total_pred == 0 or total_gold == 0:
        return 0.0

    precision = total_correct / total_pred
    recall = total_correct / total_gold

    if precision + recall == 0:
        return 0.0

    f1 = 2 * precision * recall / (precision + recall)
    return f1
