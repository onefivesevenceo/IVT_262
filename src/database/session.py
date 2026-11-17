"""Движок и фабрика коротких сессий без создания таблиц."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.configs.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
