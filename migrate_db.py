"""
Database Migration Script: SQLite to PostgreSQL
Migrates data from old SQLite database to new PostgreSQL database
"""
import sqlite3
import asyncio
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.logging import get_logger
from app.core.database import Base, sync_engine

logger = get_logger(__name__)

# Old SQLite database path
SQLITE_DB_PATH = "rag_saas.db"


def extract_sqlite_data():
    """Extract data from SQLite database."""
    logger.info(f"Connecting to SQLite database: {SQLITE_DB_PATH}")
    
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    
    data = {
        "users": [],
        "conversations": [],
        "messages": [],
    }
    
    try:
        # Extract users
        cursor.execute("SELECT * FROM users")
        data["users"] = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Extracted {len(data['users'])} users")
        
        # Extract conversations
        cursor.execute("SELECT * FROM conversations")
        data["conversations"] = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Extracted {len(data['conversations'])} conversations")
        
        # Extract messages
        cursor.execute("SELECT * FROM messages")
        data["messages"] = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Extracted {len(data['messages'])} messages")
    
    except sqlite3.Error as e:
        logger.error(f"SQLite extraction error: {e}")
    
    finally:
        sqlite_conn.close()
    
    return data


def transform_data(sqlite_data):
    """Transform SQLite data for PostgreSQL compatibility."""
    logger.info("Transforming data for PostgreSQL")
    
    transformed = {
        "users": [],
        "conversations": [],
        "messages": [],
    }
    
    # Transform users (add new fields)
    for user in sqlite_data["users"]:
        transformed["users"].append({
            "id": user["id"],
            "username": user["username"],
            "hashed_password": user["hashed_password"],
            "email": None,  # New field
            "is_active": True,  # New field
            "is_admin": False,  # New field
        })
    
    # Transform conversations (datetime format is compatible)
    for conv in sqlite_data["conversations"]:
        transformed["conversations"].append({
            "id": conv["id"],
            "user_id": conv["user_id"],
            "name": conv["name"],
            "created_at": conv["created_at"],
        })
    
    # Transform messages
    for msg in sqlite_data["messages"]:
        transformed["messages"].append({
            "id": msg["id"],
            "conversation_id": msg["conversation_id"],
            "sender": msg["sender"],
            "content": msg["content"],
            "timestamp": msg["timestamp"],
        })
    
    return transformed


async def load_postgresql_data(transformed_data):
    """Load transformed data into PostgreSQL."""
    logger.info("Loading data into PostgreSQL")
    
    # Create tables
    Base.metadata.create_all(bind=sync_engine)
    
    conn = sync_engine.connect()
    
    try:
        # Insert users
        for user in transformed_data["users"]:
            conn.execute(
                text("""
                    INSERT INTO users (id, username, hashed_password, email, is_active, is_admin)
                    VALUES (:id, :username, :hashed_password, :email, :is_active, :is_admin)
                    ON CONFLICT (id) DO NOTHING
                """),
                user
            )
        logger.info(f"Inserted {len(transformed_data['users'])} users")
        conn.commit()
        
        # Insert conversations
        for conv in transformed_data["conversations"]:
            conn.execute(
                text("""
                    INSERT INTO conversations (id, user_id, name, created_at)
                    VALUES (:id, :user_id, :name, :created_at)
                    ON CONFLICT (id) DO NOTHING
                """),
                conv
            )
        logger.info(f"Inserted {len(transformed_data['conversations'])} conversations")
        conn.commit()
        
        # Insert messages
        for msg in transformed_data["messages"]:
            conn.execute(
                text("""
                    INSERT INTO messages (id, conversation_id, sender, content, timestamp)
                    VALUES (:id, :conversation_id, :sender, :content, :timestamp)
                    ON CONFLICT (id) DO NOTHING
                """),
                msg
            )
        logger.info(f"Inserted {len(transformed_data['messages'])} messages")
        conn.commit()
        
        # Reset sequences for auto-increment
        logger.info("Resetting database sequences")
        conn.execute(text("SELECT setval('users_id_seq', (SELECT MAX(id) FROM users))"))
        conn.execute(text("SELECT setval('conversations_id_seq', (SELECT MAX(id) FROM conversations))"))
        conn.execute(text("SELECT setval('messages_id_seq', (SELECT MAX(id) FROM messages))"))
        conn.commit()
        
    except Exception as e:
        logger.error(f"PostgreSQL load error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


async def migrate_database():
    """Main migration function."""
    logger.info("Starting database migration")
    
    # Check if SQLite database exists
    import os
    if not os.path.exists(SQLITE_DB_PATH):
        logger.warning(f"SQLite database not found: {SQLITE_DB_PATH}")
        logger.info("Creating fresh PostgreSQL schema")
        Base.metadata.create_all(bind=sync_engine)
        return
    
    # Extract, Transform, Load
    sqlite_data = extract_sqlite_data()
    transformed_data = transform_data(sqlite_data)
    await load_postgresql_data(transformed_data)
    
    logger.info("Migration completed successfully")
    
    # Create backup of old database
    backup_path = f"{SQLITE_DB_PATH}.backup"
    try:
        import shutil
        shutil.copy(SQLITE_DB_PATH, backup_path)
        logger.info(f"Backup created: {backup_path}")
    except Exception as e:
        logger.warning(f"Failed to create backup: {e}")


if __name__ == "__main__":
    asyncio.run(migrate_database())
