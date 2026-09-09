from io import BytesIO
from google.cloud import storage
import pandas as pd

def read_csv_from_gcs(bucket_name, object_name):
    payload = storage.Client().bucket(bucket_name).blob(object_name).download_as_bytes()
    return pd.read_csv(BytesIO(payload),dtype=str,keep_default_na=False,na_filter=False,)

# Manual testing (shell, from repo root: python development/demo_gcs_reader.py)
if __name__ == "__main__":
    df = read_csv_from_gcs(
        "travel-incoming-gcp-evening-batch-501811",
        "incoming/employee_travel_20260907.csv",
    )
    print(df)
    print(f"Total records: {len(df)}")