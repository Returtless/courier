#!/usr/bin/env python3
"""
Automatically apply database migrations using Alembic
This script should be run before starting the application
"""
import os
import sys
import logging
from alembic.config import Config
from alembic import command
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def wait_for_postgres(db_url: str, max_retries: int = 30, retry_delay: int = 2):
    """Ожидание готовности PostgreSQL"""
    from sqlalchemy import create_engine, text
    import time
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(db_url, connect_args={"connect_timeout": 2})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ PostgreSQL готов к подключению")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.info(f"⏳ Ожидание PostgreSQL... (попытка {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ PostgreSQL не готов после {max_retries} попыток: {e}")
                return False
    return False


def run_migrations():
    """Run all pending migrations"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Check if DATABASE_URL is set
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL environment variable is not set")
            logger.error("Установите DATABASE_URL в файле env или переменных окружения")
            return False
        
        logger.info("🔄 Starting database migrations...")
        logger.info(f"📊 Database: {db_url.split('@')[1] if '@' in db_url else 'local'}")
        
        # Если используется PostgreSQL, ждем готовности
        if "postgresql" in db_url or "postgres" in db_url:
            logger.info("⏳ Ожидание готовности PostgreSQL...")
            if not wait_for_postgres(db_url):
                logger.error("❌ Не удалось подключиться к PostgreSQL. Проверьте, что база данных запущена.")
                return False
        
        # Create Alembic config
        logger.info("📝 Создание конфигурации Alembic...")
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        # Настраиваем логирование Alembic на stdout
        import logging as alembic_logging
        alembic_logger = alembic_logging.getLogger('alembic')
        alembic_logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(levelname)-5.5s [%(name)s] %(message)s'))
        alembic_logger.addHandler(handler)
        
        # Проверяем текущую версию через прямой SQL запрос (если таблица существует)
        current_version = None
        try:
            from sqlalchemy import create_engine, text, inspect
            from sqlalchemy.exc import ProgrammingError
            engine = create_engine(db_url)
            inspector = inspect(engine)
            
            # Проверяем, существует ли таблица alembic_version
            # Используем безопасную проверку через информацию о схеме
            has_alembic_table = False
            try:
                tables = inspector.get_table_names()
                has_alembic_table = 'alembic_version' in tables
                logger.debug(f"Список таблиц: {tables}")
            except Exception as inspect_error:
                logger.warning(f"⚠️ Не удалось проверить список таблиц через inspector: {inspect_error}")
                # Пробуем альтернативный способ - прямой SQL запрос с обработкой ошибки
                try:
                    with engine.connect() as test_conn:
                        test_conn.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
                        has_alembic_table = True
                except (ProgrammingError, Exception):
                    has_alembic_table = False
            
            if has_alembic_table:
                try:
                    with engine.begin() as conn:
                        result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                        current_version = result.scalar()
                        if current_version:
                            logger.info(f"📌 Текущая версия миграций в БД: {current_version}")
                            
                            # Если версия 002 (старая удаленная миграция), обновляем на 000
                            if current_version == '002':
                                logger.warning("⚠️ Обнаружена версия '002' (старая удаленная миграция)")
                                logger.info("🔄 Обновление версии в БД на '000'...")
                                conn.execute(text("UPDATE alembic_version SET version_num = '000'"))
                                logger.info("✅ Версия обновлена на '000'")
                                current_version = '000'
                        else:
                            logger.info("📌 Таблица alembic_version пуста - миграции не применялись")
                except (ProgrammingError, Exception) as query_error:
                    # Если запрос не выполнился (таблица может не существовать), игнорируем
                    logger.warning(f"⚠️ Не удалось проверить версию через SQL (таблица может не существовать): {query_error}")
                    logger.info("🔄 Продолжаем применение миграций...")
                    current_version = None
            else:
                logger.info("📌 Таблица alembic_version не существует - применяем миграции с нуля")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить версию миграций: {e}")
            logger.info("🔄 Продолжаем применение миграций (таблица, вероятно, не существует)...")
            current_version = None
        
        # Проверяем, нужны ли миграции
        logger.info("🔄 Проверка необходимости миграций...")
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        logger.info(f"📌 Текущая версия в БД: {current_version or 'нет (таблицы не существует)'}")
        logger.info(f"📌 Head версия: {head_rev}")
        
        # Если таблицы нет или версия не совпадает - применяем миграции
        if current_version is None:
            logger.info("🔄 Таблица alembic_version не существует - применяем все миграции с нуля...")
            try:
                command.upgrade(alembic_cfg, "head")
                logger.info("✅ Миграции применены успешно")
            except SystemExit as se:
                if se.code is None or se.code == 0:
                    logger.info("✅ Миграции применены (Alembic завершился с кодом 0)")
                else:
                    logger.error(f"❌ SystemExit с ненулевым кодом {se.code}")
                    raise
            except Exception as upgrade_error:
                logger.error(f"❌ Ошибка при применении миграций: {upgrade_error}", exc_info=True)
                raise
        elif current_version == head_rev:
            logger.info("✅ База данных уже на актуальной версии, миграции не требуются")
        else:
            logger.info(f"🔄 Применение миграций от {current_version} до {head_rev}...")
            try:
                command.upgrade(alembic_cfg, "head")
                logger.info("✅ Миграции применены успешно")
            except SystemExit as se:
                # SystemExit может быть вызван Alembic, но мы уже проверили, что миграции нужны
                if se.code is None or se.code == 0:
                    logger.info("✅ Миграции применены (Alembic завершился с кодом 0)")
                else:
                    logger.error(f"❌ SystemExit с ненулевым кодом {se.code}")
                    raise
            except Exception as upgrade_error:
                logger.error(f"❌ Ошибка при применении миграций: {upgrade_error}", exc_info=True)
                raise
        
        # Проверяем финальную версию (только если таблица существует)
        try:
            from sqlalchemy import create_engine, text, inspect
            from sqlalchemy.exc import ProgrammingError
            engine = create_engine(db_url)
            inspector = inspect(engine)
            
            # Проверяем существование таблицы перед запросом
            try:
                tables = inspector.get_table_names()
                has_alembic_table = 'alembic_version' in tables
            except Exception:
                has_alembic_table = False
            
            if has_alembic_table:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                    final_version = result.scalar()
                    logger.info(f"📌 Финальная версия миграций в БД: {final_version}")
            else:
                logger.info("📌 Таблица alembic_version еще не создана (миграции могут быть в процессе)")
        except (ProgrammingError, Exception) as e:
            logger.warning(f"⚠️ Не удалось проверить финальную версию: {e}")
        
        # Проверяем и добавляем отсутствующие столбцы в call_status (если таблица существует)
        try:
            from sqlalchemy import create_engine, text
            import sqlalchemy as sa
            engine = create_engine(db_url)
            inspector = sa.inspect(engine)
            
            if inspector.has_table('call_status'):
                logger.info("🔍 Проверка столбцов в таблице 'call_status'...")
                columns = [col['name'] for col in inspector.get_columns('call_status')]
                
                with engine.begin() as conn:
                    if 'arrival_time' not in columns:
                        logger.info("📝 Добавление столбца 'arrival_time' в таблицу 'call_status'...")
                        conn.execute(text("ALTER TABLE call_status ADD COLUMN IF NOT EXISTS arrival_time TIMESTAMP"))
                        logger.info("✅ Столбец 'arrival_time' добавлен")
                    
                    if 'is_manual_call' not in columns:
                        logger.info("📝 Добавление столбца 'is_manual_call' в таблицу 'call_status'...")
                        conn.execute(text("ALTER TABLE call_status ADD COLUMN IF NOT EXISTS is_manual_call BOOLEAN NOT NULL DEFAULT FALSE"))
                        logger.info("✅ Столбец 'is_manual_call' добавлен")
                    
                    if 'is_manual_arrival' not in columns:
                        logger.info("📝 Добавление столбца 'is_manual_arrival' в таблицу 'call_status'...")
                        conn.execute(text("ALTER TABLE call_status ADD COLUMN IF NOT EXISTS is_manual_arrival BOOLEAN NOT NULL DEFAULT FALSE"))
                        logger.info("✅ Столбец 'is_manual_arrival' добавлен")
                    
                    if 'manual_arrival_time' not in columns:
                        logger.info("📝 Добавление столбца 'manual_arrival_time' в таблицу 'call_status'...")
                        conn.execute(text("ALTER TABLE call_status ADD COLUMN IF NOT EXISTS manual_arrival_time TIMESTAMP"))
                        logger.info("✅ Столбец 'manual_arrival_time' добавлен")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить/добавить столбцы в call_status: {e}")
        
        logger.info("✅ Migrations completed successfully!")
        logger.info("📝 Функция run_migrations() возвращает True")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return False


def check_migrations_status():
    """Check current migration status"""
    try:
        load_dotenv()
        db_url = os.getenv("DATABASE_URL")
        
        if not db_url:
            logger.error("DATABASE_URL environment variable is not set")
            return
        
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        logger.info("📋 Current migration status:")
        command.current(alembic_cfg)
        
    except Exception as e:
        logger.error(f"❌ Failed to check migration status: {e}", exc_info=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_migrations_status()
    else:
        success = run_migrations()
        sys.exit(0 if success else 1)

