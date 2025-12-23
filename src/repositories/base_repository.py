"""
Базовый репозиторий для работы с БД
"""
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.orm import Session
from src.database.connection import get_db_session

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Базовый класс для репозиториев"""
    
    def __init__(self, model_class):
        """
        Args:
            model_class: SQLAlchemy модель
        """
        self.model_class = model_class
    
    def get(self, id: int, session: Session = None) -> Optional[T]:
        """Получить объект по ID"""
        if session is None:
            with get_db_session() as session:
                result = session.query(self.model_class).filter_by(id=id).first()
                if result:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                return result
        return session.query(self.model_class).filter_by(id=id).first()
    
    def get_all(self, session: Session = None) -> List[T]:
        """Получить все объекты"""
        if session is None:
            with get_db_session() as session:
                results = session.query(self.model_class).all()
                expunged_results = []
                for result in results:
                    session.refresh(result)
                    loaded_attrs = {}
                    for key, value in result.__dict__.items():
                        if not key.startswith('_sa_'):
                            loaded_attrs[key] = value
                    session.expunge(result)
                    for key, value in loaded_attrs.items():
                        object.__setattr__(result, key, value)
                    expunged_results.append(result)
                return expunged_results
        return session.query(self.model_class).all()
    
    def create(self, obj: T, session: Session = None) -> T:
        """Создать объект"""
        if session is None:
            with get_db_session() as session:
                session.add(obj)
                session.commit()
                session.refresh(obj)
                loaded_attrs = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_sa_'):
                        loaded_attrs[key] = value
                session.expunge(obj)
                for key, value in loaded_attrs.items():
                    object.__setattr__(obj, key, value)
                return obj
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj
    
    def update(self, obj: T, session: Session = None) -> T:
        """Обновить объект"""
        if session is None:
            with get_db_session() as session:
                session.add(obj)
                session.commit()
                session.refresh(obj)
                loaded_attrs = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_sa_'):
                        loaded_attrs[key] = value
                session.expunge(obj)
                for key, value in loaded_attrs.items():
                    object.__setattr__(obj, key, value)
                return obj
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj
    
    def delete(self, obj: T, session: Session = None) -> bool:
        """Удалить объект"""
        if session is None:
            with get_db_session() as session:
                session.delete(obj)
                session.commit()
                return True
        session.delete(obj)
        session.commit()
        return True

