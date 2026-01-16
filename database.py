import sqlite3

class VerificationDatabase:
    def __init__(self, db_path='verification.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verified_users (
                discord_id INTEGER PRIMARY KEY,
                uuid TEXT UNIQUE,
                ign TEXT NOT NULL,
                rank TEXT DEFAULT 'guest'
            )
        ''')
        conn.commit()
        conn.close()
    
    def add(self, discord_id: int, uuid: str, ign: str, rank: str = "guest"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO verified_users (discord_id, uuid, ign, rank) VALUES (?, ?, ?, ?)",
            (discord_id, uuid, ign, rank)
        )
        conn.commit()
        conn.close()
    
    def update(self, discord_id: int, uuid: str, ign: str, rank: str = "guest"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE verified_users SET uuid = ?, ign = ?, rank = ? WHERE discord_id = ?",
            (uuid, ign, rank, discord_id)
        )
        conn.commit()
        conn.close()
    
    def remove(self, discord_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verified_users WHERE discord_id = ?", (discord_id,))
        conn.commit()
        conn.close()
    
    def get(self, discord_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id, uuid, ign, rank FROM verified_users WHERE discord_id = ?", (discord_id,))
        result = cursor.fetchone()
        conn.close()
        return result
