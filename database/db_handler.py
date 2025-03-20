import sqlite3
from config.settings import Config

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('users.db')
        self.create_tables()

    def create_tables(self):
        self.conn.execute('''CREATE TABLE IF NOT EXISTS users
                             (user_id INT PRIMARY KEY NOT NULL,
                             banned BOOLEAN DEFAULT FALSE)''')
        self.conn.commit()

    def is_banned(self, user_id):
        cursor = self.conn.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else False

    # Add other DB methods for ban/unban/etc
