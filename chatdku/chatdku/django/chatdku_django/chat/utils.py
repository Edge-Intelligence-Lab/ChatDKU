import pandas as pd
from django.utils.text import slugify

def load_weekly_data():
    stats=pd.DataFrame(pd.read_csv("../locust_log/_stats.csv",))
    stats['Fail Rate']=(stats['Failure Count']*100)/stats['Request Count'] 
    stats.columns=[slugify(cols).replace('-','_') for cols in stats.columns]
    data = stats[['type', 'name', 'request_count', 'failure_count','average_response_time','fail_rate']].to_dict(orient='records')
    return data 