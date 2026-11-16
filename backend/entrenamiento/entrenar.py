"""Entrenamiento por lotes del árbol "aprobación" (pandas + scikit-learn).

Partición temporal: se ordena por `fecha_inscripcion`; el primer 75 % entrena
y el último 25 % evalúa. Se comparan con el árbol, sobre el mismo conjunto de
prueba, dos líneas base: la clase mayoritaria del entrenamiento y la regla
`aprobo = dominio_conceptos_curso > 0.5`.

Escribe en `DIRECTORIO_MODELOS`: el árbol exportado (`.json`), las métricas
(`.metricas.json`), `export_text` (`.txt`) y un `.joblib` local que la API
**nunca** carga.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.tree import DecisionTreeClassifier, export_text

from features.motor import config
from features.motor.estrategias.modelo import CARACTERISTICAS

from .exportar_arbol import arbol_a_json

DIRECTORIO_MODELOS = Path(__file__).resolve().parent / "modelos"

PARAMETROS_ARBOL = {"max_depth": 4, "min_samples_leaf": 20, "class_weight": "balanced"}
PROPORCION_ENTRENAMIENTO = 0.75
UMBRAL_REGLA_BASE = 0.5


def _sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _metricas(y, pred) -> dict:
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
    }


def entrenar(dataset_csv: Path, origen: Literal["sintetico", "real"], semilla: int = 42) -> dict:
    """Entrena, evalúa y exporta. Devuelve `{"version", "arbol", "metricas", "archivos"}`."""
    dataset_csv = Path(dataset_csv)
    datos = pd.read_csv(dataset_csv)
    datos["_t"] = pd.to_datetime(datos["fecha_inscripcion"], utc=True)
    datos = datos.sort_values(["_t", "usuario_id", "curso_id"], kind="mergesort").reset_index(drop=True)

    corte = int(len(datos) * PROPORCION_ENTRENAMIENTO)
    entreno, prueba = datos.iloc[:corte], datos.iloc[corte:]
    x_entreno, y_entreno = entreno[CARACTERISTICAS].astype(float), entreno["aprobo"].astype(int)
    x_prueba, y_prueba = prueba[CARACTERISTICAS].astype(float), prueba["aprobo"].astype(int)

    modelo = DecisionTreeClassifier(**PARAMETROS_ARBOL, random_state=semilla)
    validacion = StratifiedKFold(n_splits=5, shuffle=True, random_state=semilla)
    f1_cv = cross_val_score(clone(modelo), x_entreno, y_entreno, cv=validacion, scoring="f1")
    modelo.fit(x_entreno, y_entreno)
    pred = modelo.predict(x_prueba)

    mayoritaria = int(y_entreno.mode().iloc[0])
    pred_mayoritaria = [mayoritaria] * len(y_prueba)
    pred_regla = (x_prueba["dominio_conceptos_curso"] > UMBRAL_REGLA_BASE).astype(int)
    base_mayoritaria = {**_metricas(y_prueba, pred_mayoritaria), "clase": mayoritaria}
    base_regla = _metricas(y_prueba, pred_regla)

    version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    metricas = {
        **_metricas(y_prueba, pred),
        "matriz_confusion": confusion_matrix(y_prueba, pred, labels=[0, 1]).tolist(),
        "f1_cv_media": float(f1_cv.mean()),
        "f1_cv_desviacion": float(f1_cv.std()),
        "f1_baseline_mayoritaria": base_mayoritaria["f1"],
        "f1_baseline_regla": base_regla["f1"],
        "baselines": {"mayoritaria": base_mayoritaria, "regla_dominio": base_regla},
        "n_train": int(len(entreno)),
        "n_test": int(len(prueba)),
        "tasa_positivos": float(datos["aprobo"].mean()),
        "tasa_positivos_train": float(y_entreno.mean()),
        "tasa_positivos_test": float(y_prueba.mean()),
        "origen": origen,
        "semilla": semilla,
        "dataset_sha256": _sha256(dataset_csv),
        "umbral_etiqueta": config.UMBRAL_ETIQUETA_APROBO,
        "parametros": {**PARAMETROS_ARBOL, "random_state": semilla},
        "caracteristicas": list(CARACTERISTICAS),
        "version": version,
    }
    arbol = arbol_a_json(modelo, CARACTERISTICAS)

    DIRECTORIO_MODELOS.mkdir(parents=True, exist_ok=True)
    base = DIRECTORIO_MODELOS / f"{config.MODELO_NOMBRE}-{version}"
    archivos = {
        "arbol": base.with_name(base.name + ".json"),
        "metricas": base.with_name(base.name + ".metricas.json"),
        "texto": base.with_name(base.name + ".txt"),
        "joblib": base.with_name(base.name + ".joblib"),
    }
    archivos["arbol"].write_text(json.dumps(arbol, ensure_ascii=False, indent=2), encoding="utf-8")
    archivos["metricas"].write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
    archivos["texto"].write_text(export_text(modelo, feature_names=CARACTERISTICAS), encoding="utf-8")
    joblib.dump(modelo, archivos["joblib"])

    return {
        "version": version,
        "arbol": arbol,
        "metricas": metricas,
        "archivos": {k: str(v) for k, v in archivos.items()},
    }
