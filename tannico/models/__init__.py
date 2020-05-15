"""base for SQLAlchemy models."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

engine = create_engine(os.environ["SQLALCHEMY_DATABASE_URI"])
Session = sessionmaker(bind=engine)
