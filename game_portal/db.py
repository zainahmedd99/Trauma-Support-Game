import mysql.connector
from config import DB_CONFIG

def get_conn():
    return mysql.connector.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        passwd=DB_CONFIG['password'],
        db=DB_CONFIG['database'],
        charset=DB_CONFIG['charset'],
        use_unicode=True
    )
