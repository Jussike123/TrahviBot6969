import sqlite3
import os

# Allow overriding the database file path via environment variable (useful for hosting)
DATABASE_FILE = os.getenv('DATABASE_FILE', 'data/citations.db')

def _add_column_if_missing(conn, table_name, column_name, data_type):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}")


def init_database():
    """Initialize the SQLite database with required tables"""
    os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # Laws table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS laws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        fine_amount REAL NOT NULL,
        description TEXT
    )
    """)
    
    # Citations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS citations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name TEXT NOT NULL,
        discord_id INTEGER NOT NULL,
        total_fine REAL NOT NULL,
        laws_broken TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paid BOOLEAN DEFAULT 0,
        cited_by_id INTEGER,
        cited_by_name TEXT
    )
    """)
    
    # Player table for ID/RP pairing
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_bank (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id INTEGER NOT NULL UNIQUE,
        player_name TEXT NOT NULL
    )
    """)
    
    conn.commit()
    _add_column_if_missing(conn, "citations", "cited_by_id", "INTEGER")
    _add_column_if_missing(conn, "citations", "cited_by_name", "TEXT")
    conn.commit()
    conn.close()

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DATABASE_FILE)


def insert_law(name, fine_amount, description=""):
    """Insert a new law into the database"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO laws (name, fine_amount, description) VALUES (?, ?, ?)",
        (name, fine_amount, description)
    )
    conn.commit()
    conn.close()

def get_all_laws():
    """Get all laws from database"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, fine_amount FROM laws ORDER BY name")
    laws = cursor.fetchall()
    conn.close()
    return laws

def insert_citation(player_name, discord_id, total_fine, laws_broken, cited_by_id=None, cited_by_name=None):
    """Insert a new citation"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO citations (player_name, discord_id, total_fine, laws_broken, cited_by_id, cited_by_name) VALUES (?, ?, ?, ?, ?, ?)",
        (player_name, discord_id, total_fine, laws_broken, cited_by_id, cited_by_name)
    )
    conn.commit()
    conn.close()


def get_citations_by_discord_id(discord_id):
    """Retrieve citation history for a specific Discord user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, player_name, discord_id, total_fine, laws_broken, created_at, paid, cited_by_id, cited_by_name FROM citations WHERE discord_id = ? ORDER BY created_at DESC",
        (discord_id,)
    )
    citations = cursor.fetchall()
    conn.close()
    return citations


def player_exists(discord_id):
    """Check whether a player already exists."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM player_bank WHERE discord_id = ?", (discord_id,))
    found = cursor.fetchone() is not None
    conn.close()
    return found


def add_player(discord_id, player_name):
    """Add a player record to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO player_bank (discord_id, player_name) VALUES (?, ?)",
        (discord_id, player_name)
    )
    conn.commit()
    conn.close()


def remove_player(discord_id):
    """Remove a player record from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM player_bank WHERE discord_id = ?", (discord_id,))
    conn.commit()
    conn.close()


def get_player_by_discord_id(discord_id):
    """Return player record by Discord ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT discord_id, player_name FROM player_bank WHERE discord_id = ?",
        (discord_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully!")
