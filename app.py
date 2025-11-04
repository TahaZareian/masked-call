import os
from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)


def get_db_connection():
    """ایجاد اتصال به دیتابیس از طریق environment variables"""
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')

    # بررسی وجود تمام environment variables
    if not all([db_host, db_port, db_name, db_user, db_password]):
        missing_vars = []
        if not db_host:
            missing_vars.append('DB_HOST')
        if not db_port:
            missing_vars.append('DB_PORT')
        if not db_name:
            missing_vars.append('DB_NAME')
        if not db_user:
            missing_vars.append('DB_USER')
        if not db_password:
            missing_vars.append('DB_PASSWORD')
        print(
            f"خطا: environment variables زیر تنظیم نشده‌اند: "
            f"{', '.join(missing_vars)}"
        )
        return None

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
