import sqlite3

def check_db():
    try:
        conn = sqlite3.connect('sql_app.db')
        cursor = conn.cursor()
        
        print("Checking team_messages table structure:")
        cursor.execute("PRAGMA table_info(team_messages)")
        for row in cursor.fetchall():
            print(row)
            
        print("\nChecking for messages:")
        cursor.execute("SELECT * FROM team_messages")
        messages = cursor.fetchall()
        if not messages:
            print("No messages found yet.")
        for msg in messages:
            print(msg)
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
