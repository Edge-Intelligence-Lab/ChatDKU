import pandas as pd
from django.utils.text import slugify
from django.conf import settings
import os

def load_weekly_data():
    csv_path = os.path.join(settings.BASE_DIR, "locust_log", "_stats.csv")
    stats=pd.DataFrame(pd.read_csv(csv_path))
    stats['Fail Rate']=(stats['Failure Count']*100)/stats['Request Count'] 
    stats.columns=[slugify(cols).replace('-','_') for cols in stats.columns]
    data = stats[['type', 'name', 'request_count', 'failure_count','average_response_time','fail_rate']].to_dict(orient='records')
    return data 