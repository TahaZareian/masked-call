import os
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import Json
from asterisk_manager import AsteriskManager
from trunk_config import TrunkConfig

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


def init_trunks_table():
    """ایجاد جدول trunks در دیتابیس در صورت عدم وجود"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trunks (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                config JSONB NOT NULL,
                asterisk_config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول trunks: {e}")
        if conn:
            conn.close()
        return False


@app.route('/api/asterisk/trunk', methods=['POST'])
def create_trunk():
    """ایجاد trunk جدید و ذخیره در دیتابیس"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ارسالی نامعتبر است'
            }), 400

        trunk_name = data.get('name')
        if not trunk_name:
            return jsonify({
                'status': 'error',
                'message': 'نام trunk الزامی است'
            }), 400

        # خواندن پیکربندی از request یا environment
        if 'config' in data:
            config = TrunkConfig.from_dict(data['config'])
        else:
            # ساخت پیکربندی از فیلدهای جداگانه
            config = {
                'type': data.get('type', 'friend'),
                'send_rpid': data.get('send_rpid', 'yes'),
                'send_early_media': data.get('send_early_media', 'yes'),
                'qualify': data.get('qualify', 'yes'),
                'port': data.get('port', '5060'),
                'nat': data.get('nat', 'force_rport,comedia'),
                'insecure': data.get('insecure', 'port,invite'),
                'host': data.get('host', ''),
                'fromuser': data.get('fromuser', ''),
                'username': data.get('username', ''),
                'secret': data.get('secret', ''),
                'disallow': data.get('disallow', 'all'),
                'context': data.get('context', 'from-trunk'),
                'allow': data.get('allow', 'ulaw,alaw'),
            }

        # اعتبارسنجی
        is_valid, error_msg = TrunkConfig.validate(config)
        if not is_valid:
            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 400

        # ساخت فایل پیکربندی Asterisk
        asterisk_config = TrunkConfig.to_asterisk_config(trunk_name, config)

        # ذخیره در دیتابیس
        init_trunks_table()
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'message': 'خطا در اتصال به دیتابیس'
            }), 500

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trunks (name, config, asterisk_config)
                VALUES (%s, %s, %s)
                ON CONFLICT (name)
                DO UPDATE SET
                    config = EXCLUDED.config,
                    asterisk_config = EXCLUDED.asterisk_config,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, created_at, updated_at
            """, (trunk_name, Json(config), asterisk_config))

            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({
                'status': 'success',
                'message': f'Trunk {trunk_name} با موفقیت ذخیره شد',
                'trunk': {
                    'name': trunk_name,
                    'id': result[0],
                    'created_at': result[1].isoformat(),
                    'updated_at': result[2].isoformat()
                },
                'asterisk_config': asterisk_config
            }), 200
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return jsonify({
                'status': 'error',
                'message': f'خطا در ذخیره trunk: {str(e)}'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/trunk/config', methods=['GET'])
def get_trunk_config_from_env():
    """دریافت پیکربندی trunk از environment variables"""
    try:
        trunk_name = request.args.get('name', 'default')
        config = TrunkConfig.from_environment(trunk_name)

        if not config.get('host'):
            return jsonify({
                'status': 'error',
                'message': 'پیکربندی trunk در environment variables یافت نشد'
            }), 404

        asterisk_config = TrunkConfig.to_asterisk_config(trunk_name, config)

        return jsonify({
            'status': 'success',
            'trunk_name': trunk_name,
            'config': config,
            'asterisk_config': asterisk_config
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/trunks/db', methods=['GET'])
def list_trunks_from_db():
    """دریافت لیست trunk‌ها از دیتابیس"""
    try:
        init_trunks_table()
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'message': 'خطا در اتصال به دیتابیس'
            }), 500

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, config, asterisk_config,
                       created_at, updated_at
                FROM trunks
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            trunks = []
            for row in rows:
                trunks.append({
                    'id': row[0],
                    'name': row[1],
                    'config': row[2],
                    'asterisk_config': row[3],
                    'created_at': row[4].isoformat() if row[4] else None,
                    'updated_at': row[5].isoformat() if row[5] else None
                })

            return jsonify({
                'status': 'success',
                'trunks': trunks,
                'count': len(trunks)
            }), 200
        except Exception as e:
            if conn:
                conn.close()
            return jsonify({
                'status': 'error',
                'message': f'خطا: {str(e)}'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/trunk/db/<trunk_name>', methods=['GET'])
def get_trunk_from_db(trunk_name):
    """دریافت پیکربندی trunk از دیتابیس"""
    try:
        init_trunks_table()
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'message': 'خطا در اتصال به دیتابیس'
            }), 500

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, config, asterisk_config,
                       created_at, updated_at
                FROM trunks
                WHERE name = %s
            """, (trunk_name,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if not row:
                return jsonify({
                    'status': 'error',
                    'message': f'Trunk {trunk_name} یافت نشد'
                }), 404

            return jsonify({
                'status': 'success',
                'trunk': {
                    'id': row[0],
                    'name': row[1],
                    'config': row[2],
                    'asterisk_config': row[3],
                    'created_at': row[4].isoformat() if row[4] else None,
                    'updated_at': row[5].isoformat() if row[5] else None
                }
            }), 200
        except Exception as e:
            if conn:
                conn.close()
            return jsonify({
                'status': 'error',
                'message': f'خطا: {str(e)}'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
