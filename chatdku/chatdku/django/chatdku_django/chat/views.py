from rest_framework.decorators import api_view 
from rest_framework.response import Response
from chatdku.core.agent import Agent
from django.http import StreamingHttpResponse
from chat.models import Feedback
from chatdku.backend.user_data_interface import update
from chatdku_django.celery import redis_client
from chat.serializer import SourceSerializer

import logging
logger=logging.getLogger(__name__)



# Create your views here.
@api_view(['POST'])
def chat(request):
    
    messages = request.data.get("messages", [])
    question_id = request.data.get("chatHistoryId")
    mode = request.data.get("mode", "default")
    max_iteration = 2 if mode == "agent" else 1
    serializer=SourceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    docs=request.data.get("sources",['ChatDKU'])
    search_mode=serializer.validated_data['search_mode']
    netid=request.netid 
    user_id=netid if search_mode !=0 else "Chat_DKU"
    lock_key=f"user_lock:{netid}"
 

    if search_mode==1 or search_mode==2:
        if redis_client.get(lock_key):
            return Response({"error","The file is uploading"},status=423)
        
        
    if not messages:
        return Response({"error": "No message provided"}, status=400)

    try:
        message_content = messages[-1]["content"]
        # Create a new Agent instance per request
        agent = Agent(max_iterations=max_iteration, streaming=True, get_intermediate=False)
        responses_gen = agent(
            current_user_message=message_content, question_id=question_id, search_mode=search_mode, user_id=str(user_id), files=docs
        )
        def generate():
            for response in responses_gen.response:
                yield response  

        return StreamingHttpResponse(generate(), content_type="text/plain")

    except Exception as e:
        logger.error(f"Error Occured in chat: {str(e)}")
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
def save_feedback(request):
    try:
        data=request.data
        user_input=data["UserInput"]
        bot_answer = data['botAnswer']
        feedback_reason = data['feedbackReason']
        question_id = data['chatHistoryId']
        feedback = Feedback(
            user_input=user_input,
            gen_answer=bot_answer, 
            feedback_reason=feedback_reason,
            question_id=question_id,
        )

        feedback.save()
        return Response({'message': 'Feedback saved successfully'}, status=201)
    except Exception as e:
        logger.error(f"Error occured in Feedback {str(e)}")
        return Response({'message': str(e)}, status=500)
