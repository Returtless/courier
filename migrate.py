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


def run_migrations():
    """Run all pending migrations"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Check if DATABASE_URL is set
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL environment variable is not set")
            sys.exit(1)
        
        logger.info("🔄 Starting database migrations...")
        logger.info(f"📊 Database: {db_url.split('@')[1] if '@' in db_url else 'local'}")
        
        # Create Alembic config
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✅ Migrations completed successfully!")
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

