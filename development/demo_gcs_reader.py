from io import BytesIO
from google.cloud import storage
import pandas as pd

def read_csv_from_gcs(bucket_name, object_name):
    payload = storage.Client().bucket(bucket_name).blob(object_name).download_as_bytes()
    return pd.read_csv(BytesIO(payload),dtype=str,keep_default_na=False,na_filter=False,)

# Manual testing (shell : python development/demo_gcs_reader.py)
df = read_csv_from_gcs("travel-incoming-gcp-evening-batch-501811","incoming/employee_travel_20260907.csv")

print(df)
print(f"Total records: {len(df)}")