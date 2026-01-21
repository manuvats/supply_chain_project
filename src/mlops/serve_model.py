"""
Phase 3.2: Model Serving via FastAPI
Loads production model from MLflow, serves predictions
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mlflow
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional
import uvicorn

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
MLFLOW_URI = f"file:///{PROJECT_ROOT / 'mlruns'}".replace("\\", "/")
MODEL_NAME = "demand_forecast_model"

app = FastAPI(title="Demand Forecast API", version="1.0")

# Global model (loaded once at startup)
model = None


class PredictionRequest(BaseModel):
    """Single prediction input."""
    day_of_week: int
    day_of_year: int
    month: int
    is_promo: bool
    lag_7: float
    lag_14: float
    lag_30: float
    rolling_mean_7: float
    rolling_std_7: float
    rolling_mean_14: float
    rolling_std_14: float
    rolling_mean_30: float
    rolling_std_30: float


class BatchRequest(BaseModel):
    """Batch prediction input."""
    instances: List[PredictionRequest]


class PredictionResponse(BaseModel):
    prediction: float
    model_version: str


class BatchResponse(BaseModel):
    predictions: List[float]
    model_version: str


# Replace the load_model function (lines 56-68) with:

def load_model():
    """Load model from local file."""
    global model
    import joblib
    
    # Load best local model (XGBoost or LightGBM)
    model_path = PROJECT_ROOT / "models" / "xgboost_demand.joblib"
    if not model_path.exists():
        model_path = PROJECT_ROOT / "models" / "lightgbm_demand.joblib"
    
    if model_path.exists():
        model = joblib.load(model_path)
        print(f"✓ Loaded model from {model_path}")
    else:
        raise FileNotFoundError("No model found in models/ directory")


@app.on_event("startup")
async def startup():
    load_model()


@app.get("/health")
def health():
    return {"status": "healthy", "model_loaded": model is not None}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest):
    if model is None:
        raise HTTPException(503, "Model not loaded")
    
    features = pd.DataFrame([{
        "day_of_week": request.day_of_week,
        "day_of_year": request.day_of_year,
        "month": request.month,
        "is_promo": int(request.is_promo),
        "lag_7": request.lag_7,
        "lag_14": request.lag_14,
        "lag_30": request.lag_30,
        "rolling_mean_7": request.rolling_mean_7,
        "rolling_std_7": request.rolling_std_7,
        "rolling_mean_14": request.rolling_mean_14,
        "rolling_std_14": request.rolling_std_14,
        "rolling_mean_30": request.rolling_mean_30,
        "rolling_std_30": request.rolling_std_30,
    }])
    
    pred = model.predict(features)[0]
    return PredictionResponse(prediction=float(pred), model_version="Production")


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(request: BatchRequest):
    if model is None:
        raise HTTPException(503, "Model not loaded")
    
    records = [{
        "day_of_week": r.day_of_week,
        "day_of_year": r.day_of_year,
        "month": r.month,
        "is_promo": int(r.is_promo),
        "lag_7": r.lag_7,
        "lag_14": r.lag_14,
        "lag_30": r.lag_30,
        "rolling_mean_7": r.rolling_mean_7,
        "rolling_std_7": r.rolling_std_7,
        "rolling_mean_14": r.rolling_mean_14,
        "rolling_std_14": r.rolling_std_14,
        "rolling_mean_30": r.rolling_mean_30,
        "rolling_std_30": r.rolling_std_30,
    } for r in request.instances]
    
    df = pd.DataFrame(records)
    preds = model.predict(df).tolist()
    return BatchResponse(predictions=preds, model_version="Production")


@app.post("/reload")
def reload_model():
    """Hot-reload model (after new deployment)."""
    load_model()
    return {"status": "reloaded"}


if __name__ == "__main__":
    # Run: python serve_model.py
    uvicorn.run(app, host="0.0.0.0", port=8000)
