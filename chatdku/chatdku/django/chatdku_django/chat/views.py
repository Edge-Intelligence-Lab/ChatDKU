from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework import viewsets
from chatdku.core.agent import Agent
from django.http import StreamingHttpResponse
from chatdku_django.celery import redis_client
from chat.serializer import SourceSerializer,ChatMessageSerializer,SessionSerializer,SessionVerifierSerializer,FeedbackSerializer
from chat.models import UserSession, ChatMessages
from django.contrib.auth import get_user_model
from chat.utils import title_gen
import asyncio
from chat.utils import load_conversation
from django.db.models import Q
from drf_spectacular.utils import extend_schema_view,OpenApiExample, OpenApiParameter, extend_schema,OpenApiResponse
from openinference.instrumentation import suppress_tracing


import logging
logger=logging.getLogger(__name__)

User = get_user_model()

PARAMETERS=[
            OpenApiParameter(
                name='UID',
                location=OpenApiParameter.HEADER,
                description='NetID of the user',
                required=True,
                type=str
            ),
            OpenApiParameter(
                name='X-DisplayName',
                location=OpenApiParameter.HEADER,
                description='Display Name of the user',
                required=False,
                type=str
            )
        ]

# Create your views here
@extend_schema_view(
        post=extend_schema(description="chat route for ChatDKU. This is responsible for answering the query.",
        parameters=PARAMETERS,
        request={
            'application/json':{
                "type":'object',
                'properties':{
                    'mode':{
                        'type':'string'
                    },
                    'messages':{
                        'type':'array',
                        'items':{
                            'type':'object',
                            'properties':{
                                'content':{'type':'string'}
                            },
                            'required':['content']
                        }
                    },

                    'chatHistoryId':{
                        'type':'string',
                        'format':'uuid'
                    }
                },
                'required':['mode','messages','chatHistoryId']
            }
        },
        responses={
            200: OpenApiResponse(response={
                    'type':'string'
                }  
                )
            },
        examples=[
            OpenApiExample(
                "Request Example",
                value={
                                    
                    "mode":"default",
                    "messages":[{"content":"How do I cr/nc??"}],
                    "chatHistoryId":"692f...."

                }
            ),
            OpenApiExample(
                "Response Example",
                value=(
                    "To change a course to **Credit/No Credit (CR/NC)** at "
                    "Duke Kunshan University (DKU), follow these steps..."
                ),
            )
        ]
        )
)
class ChatView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        
        messages = request.data.get("messages", [])
        chatHistoryId=request.data.get("chatHistoryId")
        if not chatHistoryId:
            return Response({"error":"Could not get chatHistoryId"},status=400)
        
        session_serializer = SessionVerifierSerializer(
            data=request.data,
            context={'user': request.user}
        )
        session_serializer.is_valid(raise_exception=True)

        # Extract UUID
        chatHistoryId = session_serializer.validated_data["chatHistoryId"]

        session=UserSession.objects.get(id=chatHistoryId)
        test=request.data.get("test",False)

        mode = request.data.get("mode", "default")
        max_iteration = 2 if mode == "agent" else 1
        source_serializer=SourceSerializer(data=request.data)
        source_serializer.is_valid(raise_exception=True)
        search_mode,docs=source_serializer.validated_data['search_mode'],source_serializer.validated_data['docs']
        netid=request.netid 
        user_id=netid if search_mode !=0 else "Chat_DKU"
        lock_key=f"user_lock:{netid}"

    
        if search_mode==1 or search_mode==2:
            if redis_client.get(lock_key):
                return Response({"error":"The file is uploading"},status=423)
            
            
        if not messages:
            return Response({"error": "No message provided"}, status=400)

        try:
            message_content = messages[-1]["content"]
            chat_serializer=ChatMessageSerializer(
                data={
                    "role":ChatMessages.USER,
                    "message":message_content
                }
            )
            chat_serializer.is_valid(raise_exception=True)
            chat_serializer.save(session=session)
            if not session.title:

                try:
                    loop = asyncio.get_event_loop()
                    title = loop.run_until_complete(title_gen(message_content)) # Async to prevent further latency
                except Exception as e: #Fallback incase error
                    logger.error(f"Error in title Generation: {e}")
                    title=message_content
            # Create a new Agent instance per request

            conversation=load_conversation(request.user,chatHistoryId)
            if test:
                with suppress_tracing():    
                    agent = Agent(max_iterations=max_iteration, streaming=True, get_intermediate=False,previous_conversation=conversation)
                    responses_gen =agent(
                        current_user_message=message_content, question_id=chatHistoryId, search_mode=search_mode, user_id=str(user_id), files=docs
                    )
            else:
                agent = Agent(max_iterations=max_iteration, streaming=True, get_intermediate=False,previous_conversation=conversation)
                responses_gen =agent(
                    current_user_message=message_content, question_id=chatHistoryId, search_mode=search_mode, user_id=str(user_id), files=docs
                    )
            if not session.title:
                    UserSession.objects.filter(
                        id=session.id,
                        title=""
                    ).update(title=title)

            def generate():
                response_text = ""

                try:

                    for response in responses_gen.response:
                        response_text+=response
                        yield response  

                finally:
                    if response_text:

                        bot_serializer = ChatMessageSerializer(
                            data={
                                "role": ChatMessages.BOT,
                                "message": response_text
                            }
                        )
                        bot_serializer.is_valid(raise_exception=True)
                        bot_serializer.save(session=session)

            return StreamingHttpResponse(generate(), content_type="text/plain")

        except Exception as e:
            logger.error(f"Error Occured in chat: {str(e)}")
            return Response({"error": str(e)}, status=500)


@extend_schema_view(
    post=extend_schema(
        description="Post fot feedback",
        parameters=PARAMETERS,
        request={
            "application/json":{
                "type":"object",
                "properties":{
                    'userInput':{
                        'type':'string'
                    },
                    'botAnswer':{
                        'type':'string'
                    },
                    'feedbackReason':{
                        'type':'string'
                    },
                    'chatHistoryId':{
                        'type':'string',
                        'format':'uuid'
                    }
                }
            }
        },
        responses = {
            201: OpenApiResponse(
                response={
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'},
                    },
                    'example': {'message': 'Chat created successfully.'}
                },
                description='Successful chat creation response.'
            )
        }
    )
)
class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FeedbackSerializer

    def post(self, request):
        try:
            serializer = self.serializer_class(
                data={
                    "user_input": request.data.get("userInput"),
                    "gen_answer": request.data.get("botAnswer"),
                    "feedback_reason": request.data.get("feedbackReason"),
                    "question_id": str(request.data.get("chatHistoryId")),
                }
            )

            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                {"message": "Feedback saved successfully"},
                status=201
            )

        except Exception as e:
            logger.error(f"Error occurred in Feedback {str(e)}")
            return Response(
                {"message": str(e)},
                status=500
            )


@extend_schema_view(
        get=extend_schema(
            description="GET request for session",
            parameters=PARAMETERS,
            responses={
                200:OpenApiResponse(response={
                    'type':'object',
                    'properties':{
                        'session_id':{
                            'type':'string',
                            'format':'uuid'
                        }
                    }
                })
            }
        )   
)


class SessionViewSet(viewsets.ModelViewSet):
    serializer_class=SessionSerializer
    http_method_names = ["get", "head", "options","post"]


    @extend_schema(
            description="All the session_id for a user",
            parameters=PARAMETERS
    )
    def get_queryset(self):
        return UserSession.objects.filter(Q(user=self.request.user)).exclude(Q(title='')|Q(title__isnull=True)).order_by('-created_at')
    
    
    @extend_schema(
        description="Create a new chat session",
        responses={201: OpenApiResponse(response={"session_id": "uuid"})},
    )
    @action(methods=["GET"], detail=False)
    def create_session(self, request):
        session = UserSession.objects.create(user=request.user)
        return Response(
            {"session_id": str(session.id)},
            status=201
        )

    @extend_schema(
            parameters=PARAMETERS
    )
    def create(self,*args, **kwargs):
        raise MethodNotAllowed("Cannot Create a Session!")


    @extend_schema(
            description="Messages from a session_id",
            parameters=PARAMETERS,
            responses={
                200:OpenApiResponse(response={
                    'type':'object',
                    "properties":{
                        'id':{
                            'type':'integer'
                        },
                        'role':{
                            'type':'string',
                        },
                        'message':{
                            'type':'string'
                        },
                        "created_at":{
                            'type':'string',
                            'format':'date-time'
                        }
                        
                    }
                })
            }
    )
    @action(methods=['GET'],detail=True)
    def messages(self,request,pk=None):
        session=self.get_object()
        msgs=session.messages.all()
        serializer=ChatMessageSerializer(msgs,many=True)
        return Response(serializer.data)

