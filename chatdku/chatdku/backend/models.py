from agent_app import db

class Feedback(db.Model):
    __tablename__="feedback"
    id=db.Column(db.Integer,primary_key=True)
    date=db.Column(db.DateTime)
    user_input=db.Column(db.String,nullable=False)
    bot_answer=db.Column(db.String)
    feedback_reason=db.Column(db.String)
    question_id=db.Column(db.Integer)

