from db import get_conn

try:
    conn = get_conn()
    if conn.is_connected():   # check if connection really works
        print("Connected successfully!")
    else:
        print("Connection failed!")
    conn.close()
except Exception as e:
    print("Error:", e)
