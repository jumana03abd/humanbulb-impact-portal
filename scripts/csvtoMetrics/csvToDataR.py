import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS for local development with frontend frameworks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIDENCE_MAP = {
    "not at all": 1, "not at all confident": 1, "1": 1,
    "somewhat": 2, "slightly confident": 2, "2": 2,
    "very confident": 3, "very familiar": 3, "3": 3
}

def parse_rating(val) -> int:
    if pd.isna(val):
        return 0
    val_str = str(val).strip().lower()
    if val_str.isdigit():
        return int(val_str)
    return CONFIDENCE_MAP.get(val_str, 0)

def load_file(file: UploadFile) -> pd.DataFrame:
    contents = file.file.read()
    if file.filename.endswith('.csv'):
        return pd.read_csv(io.BytesIO(contents))
    elif file.filename.endswith(('.xlsx', '.xls')):
        return pd.read_excel(io.BytesIO(contents))
    else:
        raise HTTPException(400, "File format must be CSV or Excel (.xlsx)")

@app.post("/api/analyze")
async def analyze_progress(week1_file: UploadFile = File(...), week8_file: UploadFile = File(...)):
    df1 = load_file(week1_file)
    df8 = load_file(week8_file)

    # Name is in Col 2; 
    name_col = df1.columns[2]
    metric_cols = df1.columns[3:13]

    # Clean name columns
    df1['clean_name'] = df1[name_col].astype(str).str.strip().str.lower()
    df8['clean_name'] = df8[name_col].astype(str).str.strip().str.lower()

    # Inner join on Name
    merged = pd.merge(df1, df8, on='clean_name', suffixes=('_w1', '_w8'))

    metric_results = []
    total_improvements = 0
    total_comparisons = 0

    for m in metric_cols:
        col_w1 = f"{m}_w1"
        col_w8 = f"{m}_w8"
        
        improved, same, decreased, total = 0, 0, 0, 0
        
        for _, row in merged.iterrows():
            v1 = parse_rating(row[col_w1])
            v8 = parse_rating(row[col_w8])
            
            total += 1
            if v8 > v1:
                improved += 1
            elif v8 == v1:
                same += 1
            else:
                decreased += 1

        pct = round((improved / total * 100), 1) if total > 0 else 0.0
        total_improvements += improved
        total_comparisons += total

        metric_results.append({
            "metric": m,
            "improved": improved,
            "same": same,
            "decreased": decreased,
            "total": total,
            "percent_improved": pct
        })

    overall_pct = round((total_improvements / total_comparisons * 100), 1) if total_comparisons > 0 else 0.0

    return {
        "summary": {
            "total_participants": len(merged),
            "overall_improvement_rate": overall_pct
        },
        "metrics": metric_results
    }