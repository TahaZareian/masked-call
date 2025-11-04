import os
from flask import Flask, jsonify, request
import psycopg2
from asterisk_manager import AsteriskManager

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
    # بررسی وجود environment variables
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')

    if not all([db_host, db_port, db_name, db_user, db_password]):
        return jsonify({
            'status': 'not ready',
            'reason': 'missing environment variables'
        }), 503

    # اگر environment variables تنظیم شده‌اند، اپلیکیشن آماده است
    return jsonify({'status': 'ready'}), 200


@app.route('/api/asterisk/connect', methods=['POST'])
def asterisk_connect():
    """اتصال به سرور Asterisk"""
    try:
        manager = AsteriskManager()
        if manager.connect():
            manager.disconnect()
            return jsonify({
                'status': 'success',
                'message': 'اتصال به Asterisk موفق بود'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'اتصال به Asterisk ناموفق بود'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/trunks', methods=['GET'])
def list_trunks():
    """دریافت لیست trunk‌ها"""
    try:
        manager = AsteriskManager()
        if not manager.connect():
            return jsonify({
                'status': 'error',
                'message': 'امکان اتصال به Asterisk وجود ندارد'
            }), 500

        trunks = manager.list_trunks()
        manager.disconnect()

        return jsonify({
            'status': 'success',
            'trunks': trunks,
            'count': len(trunks)
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/trunk/<trunk_name>', methods=['GET'])
def get_trunk_status(trunk_name):
    """دریافت وضعیت یک trunk"""
    try:
        manager = AsteriskManager()
        if not manager.connect():
            return jsonify({
                'status': 'error',
                'message': 'امکان اتصال به Asterisk وجود ندارد'
            }), 500

        status = manager.get_trunk_status(trunk_name)
        manager.disconnect()

        return jsonify({
            'status': 'success',
            'trunk': trunk_name,
            'info': status
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/trunk', methods=['POST'])
def create_trunk():
    """ایجاد trunk جدید"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ارسالی نامعتبر است'
            }), 400

        trunk_name = data.get('name')
        host = data.get('host')
        username = data.get('username')
        secret = data.get('secret')
        port = data.get('port', 5060)
        transport = data.get('transport', 'udp')

        if not all([trunk_name, host, username, secret]):
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ناقص است'
            }), 400

        manager = AsteriskManager()
        if not manager.connect():
            return jsonify({
                'status': 'error',
                'message': 'امکان اتصال به Asterisk وجود ندارد'
            }), 500

        result = manager.create_pjsip_trunk(
            trunk_name=trunk_name,
            host=host,
            username=username,
            secret=secret,
            port=port,
            transport=transport
        )
        manager.disconnect()

        if result:
            return jsonify({
                'status': 'success',
                'message': f'Trunk {trunk_name} با موفقیت ایجاد شد'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'خطا در ایجاد trunk'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
