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
                rank TEXT DEFAULT 'guest',
                guild_type DEFAULT 'none'
            )
        ''')
        conn.commit()
        conn.close()
    
    def add(self, discord_id: int, uuid: str, ign: str, rank: str = "guest", guild_type: str = "guest"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO verified_users (discord_id, uuid, ign, rank, guild_type) VALUES (?, ?, ?, ?, ?)",
            (discord_id, uuid, ign, rank, guild_type)
        )
        conn.commit()
        conn.close()
    
    def update(self, discord_id: int, uuid: str = None, ign: str = None, rank: str = None, guild_type: str = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        set_parts = []
        params = []
        if uuid is not None:
            set_parts.append("uuid = ?")
            params.append(uuid)
        if ign is not None:
            set_parts.append("ign = ?")
            params.append(ign)
        if rank is not None:
            set_parts.append("rank = ?")
            params.append(rank)
        if guild_type is not None:
            set_parts.append("guild_type = ?")
            params.append(guild_type)
        if not set_parts:
            conn.close()
            return False
        params.append(discord_id)
        query = f"UPDATE verified_users SET {', '.join(set_parts)} WHERE discord_id = ?"
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    
    def remove(self, discord_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verified_users WHERE discord_id = ?", (discord_id,))
        conn.commit()
        conn.close()
    
    def get(self, discord_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id, uuid, ign, rank, guild_type FROM verified_users WHERE discord_id = ?", (discord_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    def get_all(self) -> dict[int, dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id, uuid, ign, rank, guild_type FROM verified_users WHERE discord_id IS NOT NULL")
        results = cursor.fetchall()
        conn.close()
        
        verified = {}
        for discord_id, uuid, ign, rank, guild_type in results:
            verified[discord_id] = {
                'uuid': uuid,
                'ign': ign,
                'rank': rank,
                'guild_type': guild_type
            }
        return verified
