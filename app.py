import os
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)


def get_db_connection():
    """ایجاد اتصال به دیتابیس از طریق environment variables"""
    db_host = os.getenv(
        'DB_HOST',
        '5eb8bc27-d15f-44e2-9f39-060d7240e176.hsvc.ir'
    )
    db_port = os.getenv('DB_PORT', '30952')
    db_name = os.getenv('DB_NAME', 'postgres')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv(
        'DB_PASSWORD',
        '4fUXe5mT6kpthtcsfeJVq47iZPhVNBR6'
    )

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        return conn
    except Exception as e:
        print(f"خطا در اتصال به دیتابیس: {e}")
        return None


def get_tables():
    """دریافت لیست جداول از دیتابیس"""
    conn = get_db_connection()
    if conn is None:
        return []

    try:
        cursor = conn.cursor()
        # کوئری برای دریافت لیست جداول
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        cursor.execute(query)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return tables
    except Exception as e:
        print(f"خطا در دریافت جداول: {e}")
        if conn:
            conn.close()
        return []


@app.route('/')
def hello():
    """صفحه اصلی با نمایش پیام خوش‌آمدگویی و لیست جداول"""
    tables = get_tables()
    return jsonify({
        'message': 'سلام! خوش آمدید',
        'status': 'success',
        'tables': tables,
        'tables_count': len(tables)
    })


@app.route('/health')
def health():
    """بررسی سلامت سرویس"""
    return jsonify({'status': 'healthy'})


@app.route('/is-ready')
def is_ready():
    """بررسی آماده‌بودن سرویس"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({'status': 'ready'}), 200
    return jsonify({'status': 'not ready'}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
