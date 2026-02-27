import pandas as pd
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from chat.models import Feedback
from chatdku.config import config
import dspy


from django.db.models import Q
from chatdku.config import config
from openai import OpenAI

import os
import datetime
import dspy
import logging
import asyncio

logger=logging.getLogger(__name__)

#DSPY classes for feedback summary
class FeedbackSignature(dspy.Signature):
    """Summarize user feedback and provide supporting evidence.
    Output the summary and evidence in valid HTML format.
    - Wrap the summary in a <p> tag.
    - For evidence, use <ul> lists grouped under <h3> headings for each theme.
    - Wrap your answer between <answer> and </answer> tags for both summary and evidence
    """

    feedback_text:str=dspy.InputField(desc="A corpus of feedback dating from last 30 days")

    summary:str=dspy.OutputField(desc="A summary of all the Feedback, including the most frequently occuring, beginning with <answer> and ending with </answer>")
    evidence:str=dspy.OutputField(desc="A short evidence for frequently occuring feedback.")



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
    new_lm = dspy.LM(

        model="openai/"+config.llm,

        api_base=config.llm_url,
        api_key=config.llm_api_key,
        model_type="chat",
        max_tokens=30000,
        stop=["<|im_end|>"]
    )
    dspy.configure(lm=new_lm)


    summary_all=summarizer(feedback_text)
    text=summary_all.summary
    evidence=summary_all.evidence
    import re
    answer=re.findall(r'<answer>(.*?)</answer>',text,re.DOTALL)
    reason=re.findall(r'<answer>(.*?)</answer>',evidence,re.DOTALL)
    answer_text=''.join([a for a in answer])
    reason_text=''.join([b for b in reason])
    email_text=answer_text+'\n'+reason_text

    return email_text


TITLE_PROMPT="""
    Create a short title based on the user Query. For example:
    User: "What are the four subspaces ?"
    Response: "Four subspaces Explanation"

    User Query:

    {user_query}
    """

client=OpenAI(
    api_key=config.llm_api_key,
    base_url=config.llm_url
)


async def title_gen(user_query):
    prompt = TITLE_PROMPT.format(user_query=user_query)
    loop = asyncio.get_running_loop()

    chat_response =await loop.run_in_executor(None,lambda:client.chat.completions.create(
            model=config.llm,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
            temperature=0.7,
            top_p=0.8,
            presence_penalty=1.5,
            extra_body={
                "top_k": 10,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        ))
    
    return chat_response.choices[0].message.content


def ping_lm(message:str):
    response=client.chat.completions.create(
                model=config.llm,
                messages=[{"role": "system", "content": "This is a ping test."},
                          {"role":"user","content":message}
                          ],
                max_tokens=8192,
                temperature=0.7,
                top_p=0.8,
                presence_penalty=1.5,
                extra_body={
                    "top_k": 10,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
    return response.choices[0].message.content


def load_conversation(user,session_id):
    objects=user.usersession
    sessions=objects.filter(Q(id=session_id)).first()
    messages= sessions.messages.order_by('-created_at')[1:11]
    return_message=list(messages.values_list("role","message"))
    return_message=return_message[::-1]
    return return_message


# NOTE: This function is not being used
# def model_response(module,**kwargs):
#     active=ActiveLM.objects.first()
#     if active and active.name=="backup":
#          lm = dspy.LM(
#             model="openai/" + config.backup_llm,
#             api_base=config.backup_llm_url,
#             api_key=config.llm_api_key,
#             model_type="chat",
#             max_tokens=config.context_window,
#             temperature=config.llm_temperature,
#         )
         
#     else:
#         lm = dspy.LM(
#             model="openai/" + config.llm,
#             api_base=config.llm_url,
#             api_key=config.llm_api_key,
#             model_type="chat",
#             max_tokens=config.context_window,
#             temperature=config.llm_temperature,
#         )

#     with dspy.context():
#         return module(**kwargs)
    

    