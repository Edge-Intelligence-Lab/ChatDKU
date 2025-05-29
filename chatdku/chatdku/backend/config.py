import os
basedir=os.path.abspath(os.path.dirname(__file__))


class Config:
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URI') or \
    'sqlite:///'+os.path.join(basedir,'./database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS=False
    