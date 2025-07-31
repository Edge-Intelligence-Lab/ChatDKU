import pandas as pd
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from chat.models import Feedback
from chatdku.setup import setup

import os
import datetime
import dspy
from chatdku.core.agent import CustomClient
import logging

logger=logging.getLogger(__name__)

#DSPY classes for feedback summary
class FeedbackSignature(dspy.Signature):
    """Summarize user feedback and provide supporting evidence.
    Output the summary and evidence in valid HTML format.
    - Wrap the summary in a <p> tag.
    - For evidence, use <ul> lists grouped under <h3> headings for each theme.
    """

    feedback_text:str=dspy.InputField(desc="A corpus of feedback dating from last 30 days")

    summary:str=dspy.OutputField(desc="A summary of all the Feedback, including the most frequently occuring")
    evidence:dict[str,list[str]]=dspy.OutputField(desc="Evidence for frequently occuring feedback")

class FeedbackSummarizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predictor=dspy.Predict(FeedbackSignature)

    def forward(self,feedback_text):
        return self.predictor(feedback_text=feedback_text)
    



#email data
def load_weekly_data():
    try:
        csv_path = os.path.join(settings.BASE_DIR, "locust_log", "_stats.csv")
        stats = pd.read_csv(csv_path)
        stats['failure_percentage'] = (stats['Failure Count'] * 100) / stats['Request Count']
        stats.columns = [slugify(col).replace('-', '_') for col in stats.columns]
        data = stats[['type', 'name', 'request_count', 'failure_count', 'average_response_time', 'failure_percentage']].to_dict(orient='records')
        return data

    except Exception as e:
        logger.error(f"Error in loading weekly load data: {str(e)}")
        return {}

def feedback_summary():
    time=timezone.now()-datetime.timedelta(days=30)
    objects=Feedback.objects.filter(time__gte=time)
    feedback_text=''
    for idx,item in enumerate(objects):
        feedback_text+=f"(feedback {idx}):\nUser Question: {item.user_input}\nGeneration: {item.gen_answer}\nReason: {item.feedback_reason}\n"

    summarizer = FeedbackSummarizer()
    setup()
    client=CustomClient()

    dspy.settings.configure(
        lm=client
    )

    summary=summarizer(feedback_text)

    return summary.summary
    


