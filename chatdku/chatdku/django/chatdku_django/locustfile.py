from locust import HttpUser, task, between
import os
import dotenv
import logging
import random
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
dotenv.load_dotenv()


class ResponseLengthError(Exception):
    def __init__(self,length,min_length=100,*args):
        self.min_length=min_length
        self.length=length
        
        super().__init__(f"The length of Response is less than the min-length: {self.min_length}. Length: {self.length}. Other information: {args[0]}")

class MyUser(HttpUser):
    wait_time = between(5, 10)
    host=os.getenv('HOST')
    session_id=''
    min_length=100

    messages = [
        {"content": "What is chatDKU?"},
        {"content": "What academic resources are available?"},
        {"content": "Can I switch my major later on? How?"},
        {"content": "What resources are available for mental health support at DKU?"},
        {"content": "What are the courses of Applied Mathematics?"},
        {"content": "Tell me about study abroad opportunities."},
        {"content": "How do I cr/nc?"},
        {"content": "what is compsci 306 about?"},
        {"content": "When can I declare my Major?"},
        {"content": "What are the mandatory common core classes?"},
        {"content": "How often should I visit my advisor?"},
        {"content": "What happens if I fail a class?"},
        {"content": "What are graduation requirements?"},
        {"content": "How should I balance a double major in Applied Mathematics and Computer Science with extracurricular commitments and mental health?"},
        {"content": "How do course choices in the Applied Mathematics track affect eligibility for graduate programs in Data Science or Theoretical Physics?"},
        {"content": "What are the academic implications of switching majors late (e.g., in junior year), especially if I’ve already started upper-level courses in the previous major?"},
        {"content": "How can I use the resources at DKU (academic, mental health, and advising) to create a personalized 4-year roadmap for research and career preparation?"}
    ]

    def get_session(self):
        response=self.client.get('/api/get_session',headers=self.headers)
        return response.text
    

    def on_start(self):
        '''To Bypasss Authentication Middleware'''
        self.headers ={
                "UID": os.getenv("UID"),               
                "X-DisplayName": os.getenv("DISPLAY_NAME"),      
                "Content-Type": "application/json",
        
        }

        self.session=json.loads(self.get_session())['session_id']


    def get_doc_list(self):
        '''Get User Docs'''
        response = self.client.get('/user/user_files', headers=self.headers)
        try:
            if not response.text.strip():
                logger.warning("Empty response body from /user/user_files")
                return []
            return response.json().get('document', [])
        except Exception as e:
            logger.warning(f"Failed to parse document list: {e}. Raw response: {response.text}")
            return []

    def generate_chat(self):
        '''Simulate Different Modes'''
        mode = "default"
        message = random.choice(self.messages)
        docs = self.get_doc_list()

        if not docs:
            sources=[]
        else: 
            k = 1 if len(docs) <= 1 else random.randint(1, len(docs)-1)
            sources = random.choices(docs, k=k)

        return {
            "chatHistoryId": self.session,
            "mode": mode,
            "messages": [message],  
            "sources": sources,    
            "session_id":self.session,
            "test":True
        }

    @task
    def post_chat(self):
        '''Chat request test'''
        try:
            payload = self.generate_chat()
            
            response = self.client.post('/api/chat', json=payload, headers=self.headers)
            message=response.text
            if len(message)<self.min_length:
                raise ResponseLengthError(len(message),self.min_length,response.text)
            logger.info(f"POST /dev/django/chat | Status: {response.status_code} | Response: {len(message)}\n")
        except Exception as e:
            logger.error(f'Chat Error: {str(e)}')
            raise

