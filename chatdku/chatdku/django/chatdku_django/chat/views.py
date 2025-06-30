from rest_framework.decorators import api_view 
from rest_framework.response import Response
from chatdku.core.agent import Agent
from django.http import StreamingHttpResponse
from chat.models import Feedback

# Create your views here.
@api_view(['POST'])
def chat(request):
    messages = request.data.get("messages", [])
    question_id = request.data.get("chatHistoryId")
    mode = request.data.get("mode", "default")
    max_iteration = 2 if mode == "agent" else 1

    if not messages:
        return Response({"error": "No message provided"}, status=400)

    try:
        message_content = messages[-1]["content"]
        # Create a new Agent instance per request
        agent = Agent(max_iterations=max_iteration, streaming=True, get_intermediate=False)
        responses_gen = agent(
            current_user_message=message_content, question_id=question_id
        )

        def generate():
            for response in responses_gen.response:
                yield response  

        return StreamingHttpResponse(generate(), content_type="text/plain")

    except Exception as e:
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
        return Response({'message': str(e)}, status=500)

@api_view(['GET'])
def index(request):

    data = {
        "netid": request.session.get('netid'),
        "display_name": request.session.get('display_name'),
    }

    return Response(data)