from rest_framework import serializers
from chat.models import UserSession,ChatMessages,Feedback
from django.contrib.auth import get_user_model



User=get_user_model()


class SourceSerializer(serializers.Serializer):

    sources = serializers.ListField(
        child=serializers.CharField(), required=False, default=['ChatDKU']
    )

    def validate(self, data):
        docs = data.get('sources') or ['ChatDKU']
        try:

            if len(docs) == 1:
                search_mode = 1 if docs[0] != 'ChatDKU' else 0
            elif len(docs) > 1 and docs[0] == 'ChatDKU':
                search_mode = 2
            else:
                search_mode = 1

        except Exception as e:
            search_mode=0
        
        data['search_mode'] = search_mode
        data['docs']=docs
        return data

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model=UserSession
        fields=['id', 'title', 'created_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model=ChatMessages
        fields=['id', 'role', 'message', 'created_at']

class SessionVerifierSerializer(serializers.Serializer):
    chatHistoryId = serializers.CharField()

    def validate(self, data):
        user = self.context['user']  
        chatHistoryId = data.get('chatHistoryId')

        exists = user.usersession.filter(id=chatHistoryId).exists()
        if exists:
            return data
        else:
            raise serializers.ValidationError("Session ID not found")


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model=Feedback
        fields = [
            "user_input",
            "gen_answer",
            "feedback_reason",
            "question_id",
        ]
