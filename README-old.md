# MLOps ONNX Deploy – CI/CD con GitHub Actions, AWS S3, ECR y ECS

## 1. Descripción general

Este proyecto implementa un **sistema de despliegue automático** para un modelo de Machine Learning
en formato **ONNX**, usando:

- **GitHub Actions** para CI/CD.
- **AWS S3** para:
  - Modelo ONNX (`model.onnx`).
  - Datos de prueba (`test_data.json`).
  - Logs de predicciones (`predictions_dev.txt`, `predictions_prod.txt`).
- **AWS ECR** para almacenar imágenes Docker.
- **AWS ECS (Fargate)** + **Application Load Balancer (ALB)** para exponer dos endpoints:
  - Endpoint `dev` (rama `dev`).
  - Endpoint `prod` (rama `prod`).

La infraestructura es **agnóstica al modelo**: cambiar de modelo implica solo cambiar la
**ruta del modelo en S3 y las variables de entorno**, sin modificar código de la app,
ni pipeline, ni recursos base en AWS.

---

## 2. Arquitectura (alto nivel)

Pseudo-diagrama:

```text
           +-------------------------+
           | GitHub (repo)          |
           | branches: dev, prod    |
           +-----------+------------+
                       |
                       | push
                       v
           +-------------------------+
           | GitHub Actions          |
           |  - Job: test            |
           |  - Job: build_and_deploy|
           +-----------+-------------+
                       |
                       | docker push
                       v
   +-----------------------------+       +-------------------------+
   | AWS ECR                     |       | AWS S3                  |
   | mlops-onnx-api (repo)       |       | - model-bucket          |
   +-------------+---------------+       |   - models/current/...  |
                 |                       |   - test-data/...       |
                 |                       | - logs-bucket           |
                 |                       |   - predictions_dev.txt |
                 |                       |   - predictions_prod.txt|
                 v                       +-------------------------+
   +-----------------------------+
   | AWS ECS (Fargate)          |
   | Cluster: mlops-onnx-cluster|
   |                             |
   | Service dev  Service prod   |
   |  ENV=dev      ENV=prod      |
   +-----+-------------+---------+
         |             |
         v             v
     Target Group  Target Group
         |             |
         +------ ALB ---+
                 |
                 v
           Usuarios / clientes
```

---

## 3. Modelo ONNX usado (ejemplo)

El proyecto asume un modelo ONNX de clasificación tipo Iris:

- **Entrada:** vector `[f1, f2, f3, f4]` (floats).

- **Salida:** logits o probabilidades para 3 clases (0, 1, 2).

En la práctica, puedes usar cualquier modelo ONNX compatible con onnxruntime que:

- Reciba un tensor 2D de floats `shape: (batch_size, n_features)`.

- Devuelva logits/probabilidades o una salida numérica interpretable como clase.

La app y los tests solo asumen que:

- El modelo se puede cargar con `onnxruntime.InferenceSession`.

- Se puede inferir pasando un dict `{input_name: np.array([...])}`.

---

## 4. Estructura del repositorio
```text
app/
  main.py           # FastAPI + endpoints + integración logging
  model_loader.py   # Descarga y carga del modelo desde S3 (agnóstico)
  predictor.py      # Lógica de inferencia (single y batch)
  logging_utils.py  # Escritura de logs de predicciones en S3
  requirements.txt

tests/
  test_inference_response.py  # Verifica que el modelo responde
  test_metric_threshold.py    # Verifica que accuracy >= umbral

.github/workflows/
  ci_cd.yml         # Pipeline unificado para dev y prod

config/
  env.example       # Variables de entorno de ejemplo

infra/
  create_s3_buckets.sh
  create_ecr_repo.sh
  create_ecs_cluster_and_services.sh

Dockerfile
README.md
```

---

## 5. Flujo de CI/CD
### 5.1 Rama `dev`

1. Haces `git push` a la rama `dev`.

2. Se dispara el workflow `ci_cd.yml`.

3. Job `test`:

    - Configura credenciales AWS.

    - Descarga el modelo desde:

        - `s3://mlops-model-bucket/models/current/model.onnx`

    - Descarga los datos de prueba desde:

        - `s3://mlops-model-bucket/test-data/test_data.json`

    - Ejecuta:

        - `tests/test_inference_response.py`: verifica que el modelo responda.

        - `tests/test_metric_threshold.py`: calcula accuracy con los datos de prueba y verifica que sea ≥ MIN_ACCEPTABLE_ACCURACY (p.e. 0.7).

4. Si `test` pasa, job `build_and_deploy`:

    - Construye imagen Docker de la app FastAPI.

    - Etiqueta la imagen con `<branch>-<short_sha>` y hace push a ECR.

    - Actualiza el servicio ECS `mlops-onnx-api-dev` con la nueva imagen.

    - El ALB apunta a este servicio para el endpoint `dev`.

## 5.2 Rama `prod`

Análogo, pero:

- El servicio actualizado es `mlops-onnx-api-prod`.

- El archivo de logs en S3 será `predictions_prod.txt`.

- Normalmente se hará merge de `dev` → `prod` cuando hayas validado cambios.

---

## 6. Relación entre buckets S3 y sistema

Ejemplo de esquema:

```text
s3://mlops-model-bucket/
  ├── models/
  │   └── current/
  │       └── model.onnx
  └── test-data/
      └── test_data.json

s3://mlops-logs-bucket/
  ├── predictions_dev.txt
  └── predictions_prod.txt
```

- La app nunca contiene el `.onnx` ni el `test_data.json` en el repo:

    - Siempre se descargan desde S3.

- Logs de predicción:

    - ECS `dev` tiene `PREDICTIONS_S3_KEY=predictions_dev.txt`.

    - ECS `prod` tiene `PREDICTIONS_S3_KEY=predictions_prod.txt`.

- Cambiar de modelo implica subir un nuevo `model.onnx` a otra ruta (por ejemplo
`models/v2/model.onnx`) y actualizar `MODEL_S3_KEY` en las variables de entorno
/ secrets. El resto de la solución sigue igual.

