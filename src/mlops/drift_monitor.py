"""
Phase 3.3: Drift Monitoring (Custom Implementation)
Uses PSI and KS tests instead of Evidently
"""
import pandas as pd
import numpy as np
import duckdb
from pathlib import Path
from datetime import datetime
from scipy import stats
import json

PROJECT_ROOT = Path("C:/Users/Manu/supply_chain_project")
DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
REPORTS_DIR = PROJECT_ROOT / "reports" / "drift"

FEATURE_COLS = [
    "day_of_week", "month", "is_promo",
    "units_sold_lag_7", "units_sold_lag_14", "units_sold_lag_30",
    "units_sold_roll_mean_7", "units_sold_roll_std_7",
    "units_sold_roll_mean_14", "units_sold_roll_std_14",
    "units_sold_roll_mean_30", "units_sold_roll_std_30",
]
TARGET_COL = "units_sold"


def calculate_psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index for drift detection."""
    # Create bins from reference distribution
    _, bin_edges = np.histogram(reference, bins=bins)
    
    ref_counts, _ = np.histogram(reference, bins=bin_edges)
    cur_counts, _ = np.histogram(current, bins=bin_edges)
    
    # Convert to proportions (avoid zero)
    ref_pct = (ref_counts + 1) / (len(reference) + bins)
    cur_pct = (cur_counts + 1) / (len(current) + bins)
    
    psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return psi


def calculate_ks(reference: np.ndarray, current: np.ndarray) -> tuple:
    """Kolmogorov-Smirnov test for distribution comparison."""
    statistic, pvalue = stats.ks_2samp(reference, current)
    return statistic, pvalue


def load_data(con, cutoff_date: str, start_date: str = None, end_date: str = None):
    """Load reference and current data."""
    ref_query = f"SELECT * FROM main_features.demand_features WHERE ds < '{cutoff_date}'"
    reference = con.execute(ref_query).df().dropna(subset=FEATURE_COLS)
    
    end_clause = f"AND ds <= '{end_date}'" if end_date else ""
    cur_query = f"SELECT * FROM main_features.demand_features WHERE ds >= '{start_date or cutoff_date}' {end_clause}"
    current = con.execute(cur_query).df().dropna(subset=FEATURE_COLS)
    
    return reference, current


def analyze_drift(reference: pd.DataFrame, current: pd.DataFrame) -> dict:
    """Calculate drift metrics for all features."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "reference_rows": len(reference),
        "current_rows": len(current),
        "features": {},
        "drifted_features": [],
    }
    
    for col in FEATURE_COLS:
        ref_vals = reference[col].values.astype(float)
        cur_vals = current[col].values.astype(float)
        
        psi = calculate_psi(ref_vals, cur_vals)
        ks_stat, ks_pvalue = calculate_ks(ref_vals, cur_vals)
        
        # Drift thresholds: PSI > 0.2 or KS p-value < 0.05
        drift_detected = psi > 0.2 or ks_pvalue < 0.05
        
        results["features"][col] = {
            "psi": round(psi, 4),
            "ks_statistic": round(ks_stat, 4),
            "ks_pvalue": round(ks_pvalue, 4),
            "drift_detected": drift_detected,
        }
        
        if drift_detected:
            results["drifted_features"].append(col)
    
    # Target drift
    ref_target = reference[TARGET_COL].values
    cur_target = current[TARGET_COL].values
    target_psi = calculate_psi(ref_target, cur_target)
    target_ks, target_pval = calculate_ks(ref_target, cur_target)
    
    results["target"] = {
        "psi": round(target_psi, 4),
        "ks_statistic": round(target_ks, 4),
        "ks_pvalue": round(target_pval, 4),
        "drift_detected": target_psi > 0.2 or target_pval < 0.05,
    }
    
    # Summary
    results["drift_share"] = len(results["drifted_features"]) / len(FEATURE_COLS)
    results["dataset_drift_detected"] = results["drift_share"] > 0.3
    
    return results


def generate_html_report(results: dict, output_path: Path):
    """Generate simple HTML drift report."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Drift Report - {results['timestamp'][:10]}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        .drift {{ background: #ffcccc; }}
        .no-drift {{ background: #ccffcc; }}
        .summary {{ background: #f0f0f0; padding: 20px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>Drift Monitoring Report</h1>
    <div class="summary">
        <p><strong>Timestamp:</strong> {results['timestamp']}</p>
        <p><strong>Reference rows:</strong> {results['reference_rows']:,}</p>
        <p><strong>Current rows:</strong> {results['current_rows']:,}</p>
        <p><strong>Drift share:</strong> {results['drift_share']:.1%}</p>
        <p><strong>Dataset drift:</strong> {'⚠️ YES' if results['dataset_drift_detected'] else '✅ NO'}</p>
        <p><strong>Target drift:</strong> {'⚠️ YES' if results['target']['drift_detected'] else '✅ NO'}</p>
    </div>
    
    <h2>Feature Drift Details</h2>
    <table>
        <tr><th>Feature</th><th>PSI</th><th>KS Statistic</th><th>KS p-value</th><th>Drift</th></tr>
"""
    for col, metrics in results["features"].items():
        row_class = "drift" if metrics["drift_detected"] else "no-drift"
        drift_text = "⚠️ Yes" if metrics["drift_detected"] else "✅ No"
        html += f"""
        <tr class="{row_class}">
            <td>{col}</td>
            <td>{metrics['psi']}</td>
            <td>{metrics['ks_statistic']}</td>
            <td>{metrics['ks_pvalue']}</td>
            <td>{drift_text}</td>
        </tr>
"""
    
    # Target row
    t = results["target"]
    row_class = "drift" if t["drift_detected"] else "no-drift"
    html += f"""
        <tr class="{row_class}">
            <td><strong>{TARGET_COL} (target)</strong></td>
            <td>{t['psi']}</td>
            <td>{t['ks_statistic']}</td>
            <td>{t['ks_pvalue']}</td>
            <td>{'⚠️ Yes' if t['drift_detected'] else '✅ No'}</td>
        </tr>
    </table>
</body>
</html>
"""
    output_path.write_text(html, encoding='utf-8')


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Drift Monitoring")
    parser.add_argument("--train-cutoff", default="2024-10-01")
    parser.add_argument("--monitor-start", default="2024-10-01")
    parser.add_argument("--monitor-end", default=None)
    parser.add_argument("--threshold", type=float, default=0.3)
    args = parser.parse_args()

    con = duckdb.connect(str(DB_PATH), read_only=True)
    
    print(f"Loading reference data (before {args.train_cutoff})...")
    reference, current = load_data(con, args.train_cutoff, args.monitor_start, args.monitor_end)
    print(f"  Reference: {len(reference):,} rows")
    print(f"  Current: {len(current):,} rows")
    
    print("Analyzing drift...")
    results = analyze_drift(reference, current)
    
    # Save reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    json_path = REPORTS_DIR / f"drift_summary_{ts}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=lambda x: bool(x) if isinstance(x, (np.bool_,)) else x)
    print(f"✓ Saved: {json_path}")
    
    html_path = REPORTS_DIR / f"drift_report_{ts}.html"
    generate_html_report(results, html_path)
    print(f"✓ Saved: {html_path}")
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Drift Share: {results['drift_share']:.1%}")
    print(f"Drifted Features: {results['drifted_features']}")
    print(f"Target Drift: {results['target']['drift_detected']}")
    print(f"{'='*50}")
    
    if results['dataset_drift_detected']:
        print("⚠️  ALERT: Dataset drift detected!")
        return 1
    print("✓ No significant drift")
    return 0


if __name__ == "__main__":
    exit(main())