from flask import Flask,render_template,redirect,url_for,flash,request
from flask_bootstrap import Bootstrap5
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from sqlalchemy import Integer,String,Text
import os 
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_KEY')
Bootstrap5(app)

class Base(DeclarativeBase):
    pass
app.config["SQLARCHEMY_DATABASE_URL"]=os.getenv('DB_url')
db = SQLAlchemy()