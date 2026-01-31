import pandas as pd

CSV_PATH = "Tribal-Telugu-Text.xlsx"

try:
    df = pd.read_excel(CSV_PATH)
    print("Columns:", df.columns.tolist())
    if not df.empty:
        print("First row:", df.iloc[0].to_dict())
    else:
        print("DataFrame is empty")
except Exception as e:
    print(f"Error: {e}")
