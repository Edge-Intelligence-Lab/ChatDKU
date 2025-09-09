from rest_framework.decorators import api_view 
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from chatdku.core.agent import Agent
from django.http import StreamingHttpResponse
from chat.models import Feedback
from chatdku.backend.user_data_interface import update
from chatdku_django.celery import redis_client
from chat.serializer import SourceSerializer,ChatMessageSerializer,SessionSerializer,SessionVerifierSerializer
from chat.models import UserSession, ChatMessages
from django.contrib.auth import get_user_model
from chat.utils import title_gen
import asyncio
from chat.tasks import clean_empty_sessions

import logging
logger=logging.getLogger(__name__)

User = get_user_model()



# Create your views here.
@api_view(['POST'])
def chat(request):
    
    messages = request.data.get("messages", [])
    question_id = request.data.get("chatHistoryId")
    session_id=request.data.get("session_id")
    if not session_id:
        return Response({"error":"Could not get session_id"},status=400)
    
    serializer = SessionVerifierSerializer(
        data=request.data,
        context={'user': request.user}
    )
    serializer.is_valid(raise_exception=True)

    # Extract UUID
    session_id = serializer.validated_data["session_id"]

    session=UserSession.objects.get(id=session_id)

    mode = request.data.get("mode", "default")
    max_iteration = 2 if mode == "agent" else 1
    serializer=SourceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    search_mode,docs=serializer.validated_data['search_mode'],serializer.validated_data['docs']
    netid=request.netid 
    user_id=netid if search_mode !=0 else "Chat_DKU"
    lock_key=f"user_lock:{netid}"

 
    if search_mode==1 or search_mode==2:
        if redis_client.get(lock_key):
            return Response({"error":"The file is uploading"},status=423)
        
        
    if not messages:
        return Response({"error": "No message provided"}, status=400)

    try:
        print("1")
        message_content = messages[-1]["content"]
        ChatMessages.objects.create(session=session,role='User',message=message_content)
        print("2")
        if not session.title:

            try:
                loop = asyncio.get_event_loop()
                title = loop.run_until_complete(title_gen(message_content)) # Async to prevent further latency
            except Exception as e: #Fallback incase error
                logger.error(f"Error in title Generation: {e}")
                title=message_content
        # Create a new Agent instance per request
        agent = Agent(max_iterations=max_iteration, streaming=True, get_intermediate=False)
        responses_gen = agent(
            current_user_message=message_content, question_id=question_id, search_mode=search_mode, user_id=str(user_id), files=docs
        )
        print("3")
        if not session.title:
            session.title=title
            session.save()

        clean_empty_sessions.delay()  

        def generate():
            response_text = ""

            for response in responses_gen.response:
                response_text+=response
                yield response  

            ChatMessages.objects.create(session=session,role="Bot",message=response_text)
        return StreamingHttpResponse(generate(), content_type="text/plain")

    except Exception as e:
        logger.error(f"Error Occured in chat: {str(e)}")
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
def save_feedback(request):
    try:
        data=request.data
        user_input=data["userInput"]
        bot_answer = data['botAnswer']
        feedback_reason = data['feedbackReason']
        question_id = data['chatHistoryId']
        feedback = Feedback(
            user_input=user_input,
            gen_answer=bot_answer, 
            feedback_reason=feedback_reason,
            question_id=str(question_id),
        )

        feedback.save()
        return Response({'message': 'Feedback saved successfully'}, status=201)
    except Exception as e:
        logger.error(f"Error occured in Feedback {str(e)}")
        return Response({'message': str(e)}, status=500)
    
@api_view(['GET'])
def get_session(request):
    try:
        session=UserSession.objects.create(user=request.user)
        session_id=str(session.id)
        return Response({"session_id":session_id})
    except Exception as e:
        return Response({"error":f"Could not issue a session_id:{e}"})



class SessionViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)
    
    def create(self,*args, **kwargs):
        raise MethodNotAllowed("Cannot Create a Session!")

    serializer_class=SessionSerializer

    @action(methods=['GET'],detail=True)
    def messages(self,request,pk=None):
        session=self.get_object()
        msgs=session.messages.all()
        print(msgs)
        serializer=ChatMessageSerializer(msgs,many=True)
        return Response(serializer.data)

