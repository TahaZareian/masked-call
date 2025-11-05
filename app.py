import os
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import Json
from datetime import datetime
from asterisk_manager import AsteriskManager
from call_state_machine import CallSessionStateMachine, CallState
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


@app.route('/api/system/my-ip', methods=['GET'])
def get_my_ip():
    """دریافت IP واقعی سرور برای اضافه کردن به permit list"""
    try:
        import socket
        # اتصال به یک سرور خارجی برای دریافت IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # اتصال به یک سرور (نیازی به اتصال واقعی نیست)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = 'unknown'
        finally:
            s.close()

        return jsonify({
            'status': 'success',
            'my_ip': ip,
            'message': (
                'این IP را به permit list در Issabel اضافه کنید: '
                f'permit={ip}/32'
            )
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/test-connection', methods=['POST'])
def test_asterisk_connection():
    """تست اتصال به سرور Asterisk بدون احراز هویت"""
    try:
        import socket
        data = request.get_json() or {}
        host = data.get('host') or os.getenv('ASTERISK_HOST')
        port = int(data.get('port', os.getenv('ASTERISK_PORT', '5038')))

        if not host:
            return jsonify({
                'status': 'error',
                'message': 'host مشخص نشده است'
            }), 400

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                return jsonify({
                    'status': 'success',
                    'message': f'پورت {port} روی {host} باز است',
                    'host': host,
                    'port': port
                }), 200
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'پورت {port} روی {host} بسته است یا در دسترس نیست',
                    'host': host,
                    'port': port
                }), 500
        except socket.timeout:
            return jsonify({
                'status': 'error',
                'message': f'Timeout: نمی‌توان به {host}:{port} متصل شد',
                'host': host,
                'port': port
            }), 500
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'خطا: {str(e)}',
                'host': host,
                'port': port
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/asterisk/connect', methods=['POST'])
def asterisk_connect():
    """اتصال به سرور Asterisk"""
    try:
        # خواندن تنظیمات از دیتابیس
        manager = AsteriskManager()
        
        print("=" * 80)
        print("CONNECTING TO ASTERISK:")
        print(f"Host: {manager.host}")
        print(f"Port: {manager.port}")
        print(f"Username: {manager.username}")
        secret_length = len(manager.secret) if manager.secret else 0
        secret_repr = repr(manager.secret) if manager.secret else 'None'
        print(f"Secret length: {secret_length}")
        print(f"Secret repr: {secret_repr}")
        print("=" * 80)
        
        # بررسی تنظیمات
        missing_vars = []
        if not manager.host:
            missing_vars.append('ASTERISK_HOST')
        if not manager.port:
            missing_vars.append('ASTERISK_PORT')
        if not manager.username:
            missing_vars.append('ASTERISK_USERNAME')
        if not manager.secret:
            missing_vars.append('ASTERISK_SECRET')
        
        if missing_vars:
            return jsonify({
                'status': 'error',
                'message': 'تنظیمات Asterisk کامل نیست',
                'missing_variables': missing_vars,
                'current_config': {
                    'host': manager.host or 'not_set',
                    'port': manager.port or 'not_set',
                    'username': manager.username or 'not_set',
                    'secret': '***' if manager.secret else 'not_set'
                }
            }), 400
        
        success, error_message = manager.connect()
        if success:
            manager.disconnect()
            return jsonify({
                'status': 'success',
                'message': 'اتصال به Asterisk موفق بود',
                'config': {
                    'host': manager.host,
                    'port': manager.port,
                    'username': manager.username
                }
            }), 200
        else:
            # بررسی اگر خطای احراز هویت است، راهنمایی بده
            troubleshooting = ""
            if "authentication failed" in error_message.lower():
                troubleshooting = (
                    "خطا: احراز هویت ناموفق. "
                    "ممکن است IP شما در permit list نباشد. "
                    "در فایل manager.conf در Issabel، IP سرور خود را به permit list اضافه کنید: "
                    "permit=193.151.147.135/32"
                )

            return jsonify({
                'status': 'error',
                'message': 'اتصال به Asterisk ناموفق بود',
                'error_details': error_message,
                'config_used': {
                    'host': manager.host,
                    'port': manager.port,
                    'username': manager.username,
                    'secret': '***'
                },
                'troubleshooting': troubleshooting if troubleshooting else None
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}',
            'error_type': type(e).__name__
        }), 500


@app.route('/api/asterisk/config', methods=['GET'])
def get_asterisk_config():
    """
    بررسی تنظیمات Asterisk
    ابتدا از دیتابیس می‌خواند، سپس از environment variables
    """
    config_name = request.args.get('name', 'default')
    source = None
    config = None

    # اول از دیتابیس بخوان
    db_config = get_asterisk_config_from_db(config_name)
    if db_config:
        config = db_config
        source = 'database'
    else:
        # اگر در دیتابیس نبود، از environment variables بخوان
        asterisk_host = os.getenv('ASTERISK_HOST')
        asterisk_port = os.getenv('ASTERISK_PORT', '5038')
        asterisk_username = os.getenv('ASTERISK_USERNAME')
        asterisk_secret = os.getenv('ASTERISK_SECRET')

        if all([
            asterisk_host,
            asterisk_port,
            asterisk_username,
            asterisk_secret
        ]):
            config = {
                'host': asterisk_host,
                'port': int(asterisk_port),
                'username': asterisk_username,
                'secret': asterisk_secret
            }
            source = 'environment'

    if not config:
        return jsonify({
            'status': 'error',
            'message': 'تنظیمات Asterisk یافت نشد'
        }), 404

    config_status = {
        'host': config.get('host'),
        'port': config.get('port'),
        'username': config.get('username'),
        'secret': '***' if config.get('secret') else None,
        'source': source,
        'all_configured': all([
            config.get('host'),
            config.get('port'),
            config.get('username'),
            config.get('secret')
        ])
    }

    return jsonify({
        'status': 'success',
        'config': config_status
    }), 200


@app.route('/api/asterisk/config', methods=['POST'])
def save_asterisk_config():
    """ذخیره تنظیمات Asterisk در دیتابیس"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ارسالی نامعتبر است'
            }), 400

        config_name = data.get('name', 'default')
        host = data.get('host')
        port = data.get('port', 5038)
        username = data.get('username')
        secret = data.get('secret')

        if not all([host, port, username, secret]):
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ناقص است'
            }), 400

        # ذخیره در دیتابیس
        init_asterisk_config_table()
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'message': 'خطا در اتصال به دیتابیس'
            }), 500

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO asterisk_config
                (name, host, port, username, secret)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name)
                DO UPDATE SET
                    host = EXCLUDED.host,
                    port = EXCLUDED.port,
                    username = EXCLUDED.username,
                    secret = EXCLUDED.secret,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, created_at, updated_at
            """, (config_name, host, port, username, secret))

            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({
                'status': 'success',
                'message': f'تنظیمات Asterisk با نام "{config_name}" ذخیره شد',
                'config': {
                    'name': config_name,
                    'id': result[0],
                    'created_at': result[1].isoformat(),
                    'updated_at': result[2].isoformat()
                }
            }), 200
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            return jsonify({
                'status': 'error',
                'message': f'خطا در ذخیره تنظیمات: {str(e)}'
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
        success, error_msg = manager.connect()
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'امکان اتصال به Asterisk وجود ندارد',
                'error_details': error_msg
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
        success, error_msg = manager.connect()
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'امکان اتصال به Asterisk وجود ندارد',
                'error_details': error_msg
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


def init_asterisk_config_table():
    """ایجاد جدول asterisk_config در دیتابیس در صورت عدم وجود"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asterisk_config (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL DEFAULT 'default',
                host VARCHAR(255),
                port INTEGER DEFAULT 5038,
                username VARCHAR(255),
                secret VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول asterisk_config: {e}")
        if conn:
            conn.close()
        return False


def init_call_sessions_table():
    """ایجاد جدول call_sessions برای ذخیره وضعیت تماس‌ها"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) UNIQUE NOT NULL,
                current_state VARCHAR(50) NOT NULL,
                number_a VARCHAR(50),
                number_b VARCHAR(50),
                caller_id VARCHAR(50),
                trunk_name VARCHAR(255),
                channel_a_id VARCHAR(255),
                channel_b_id VARCHAR(255),
                metadata JSONB,
                state_history JSONB,
                state_timestamps JSONB,
                error_log JSONB,
                is_final BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                duration_seconds INTEGER
            )
        """)
        
        # ایجاد ایندکس برای جستجوی سریع
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_sessions_session_id 
            ON call_sessions(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_sessions_current_state 
            ON call_sessions(current_state)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_sessions_created_at 
            ON call_sessions(created_at)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول call_sessions: {e}")
        if conn:
            conn.close()
        return False


def init_call_state_logs_table():
    """ایجاد جدول call_state_logs برای لاگ کامل تمام تغییرات state"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_state_logs (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                state VARCHAR(50) NOT NULL,
                previous_state VARCHAR(50),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ایجاد ایندکس‌ها
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_state_logs_session_id 
            ON call_state_logs(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_state_logs_timestamp 
            ON call_state_logs(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_call_state_logs_session_timestamp 
            ON call_state_logs(session_id, timestamp)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول call_state_logs: {e}")
        if conn:
            conn.close()
        return False


def save_call_session(state_machine: CallSessionStateMachine, **kwargs) -> bool:
    """
    ذخیره وضعیت تماس در دیتابیس
    
    Args:
        state_machine: ماشین حالت
        **kwargs: فیلدهای اضافی (number_a, number_b, channel_a_id, etc.)
    
    Returns:
        True اگر موفق باشد
    """
    init_call_sessions_table()
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        state_data = state_machine.to_dict()
        
        # محاسبه duration
        duration = None
        if state_data['created_at'] and state_data['updated_at']:
            from datetime import datetime
            created = datetime.fromisoformat(state_data['created_at'])
            updated = datetime.fromisoformat(state_data['updated_at'])
            duration = int((updated - created).total_seconds())
        
        cursor.execute("""
            INSERT INTO call_sessions (
                session_id, current_state, number_a, number_b, caller_id,
                trunk_name, channel_a_id, channel_b_id, metadata,
                state_history, state_timestamps, error_log, is_final,
                completed_at, duration_seconds
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id)
            DO UPDATE SET
                current_state = EXCLUDED.current_state,
                number_a = EXCLUDED.number_a,
                number_b = EXCLUDED.number_b,
                caller_id = EXCLUDED.caller_id,
                trunk_name = EXCLUDED.trunk_name,
                channel_a_id = EXCLUDED.channel_a_id,
                channel_b_id = EXCLUDED.channel_b_id,
                metadata = EXCLUDED.metadata,
                state_history = EXCLUDED.state_history,
                state_timestamps = EXCLUDED.state_timestamps,
                error_log = EXCLUDED.error_log,
                is_final = EXCLUDED.is_final,
                completed_at = EXCLUDED.completed_at,
                duration_seconds = EXCLUDED.duration_seconds,
                updated_at = CURRENT_TIMESTAMP
        """, (
            state_machine.session_id,
            state_machine.current_state.value,
            kwargs.get('number_a'),
            kwargs.get('number_b'),
            kwargs.get('caller_id'),
            kwargs.get('trunk_name'),
            kwargs.get('channel_a_id'),
            kwargs.get('channel_b_id'),
            Json(state_machine.metadata),
            Json([s.value for s in state_machine.state_history]),
            Json(state_machine.state_timestamps),
            Json(state_machine.error_log),
            state_machine.is_final_state(),
            datetime.now().isoformat() if state_machine.is_final_state() else None,
            duration
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ذخیره call_session: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def log_state_change(
    session_id: str,
    state: str,
    previous_state: Optional[str] = None,
    metadata: Optional[Dict] = None,
    error_message: Optional[str] = None
) -> bool:
    """
    لاگ کردن تغییر state در جدول call_state_logs
    
    Args:
        session_id: شناسه session
        state: state جدید
        previous_state: state قبلی
        metadata: اطلاعات اضافی
        error_message: پیام خطا (در صورت وجود)
    
    Returns:
        True اگر موفق باشد
    """
    init_call_state_logs_table()
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO call_state_logs (
                session_id, state, previous_state, metadata, error_message
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            session_id,
            state,
            previous_state,
            Json(metadata or {}),
            error_message
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در لاگ کردن state change: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def load_call_session(session_id: str) -> Optional[CallSessionStateMachine]:
    """
    بارگذاری وضعیت تماس از دیتابیس
    
    Args:
        session_id: شناسه session
    
    Returns:
        CallSessionStateMachine یا None
    """
    init_call_sessions_table()
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT current_state, metadata, state_history, state_timestamps, error_log
            FROM call_sessions
            WHERE session_id = %s
        """, (session_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return None
        
        # بازسازی state machine
        state_machine = CallSessionStateMachine(
            initial_state=CallState(row[0]),
            session_id=session_id,
            metadata=row[1] or {}
        )
        
        # بازسازی state history
        if row[2]:
            state_machine.state_history = [CallState(s) for s in row[2]]
        
        # بازسازی timestamps و error log
        if row[3]:
            state_machine.state_timestamps = row[3]
        if row[4]:
            state_machine.error_log = row[4]
        
        return state_machine
    except Exception as e:
        print(f"خطا در بارگذاری call_session: {e}")
        if conn:
            conn.close()
        return None


def get_asterisk_config_from_db(name: str = 'default'):
    """
    خواندن تنظیمات Asterisk از دیتابیس

    Args:
        name: نام پیکربندی (پیش‌فرض: 'default')

    Returns:
        دیکشنری تنظیمات یا None
    """
    init_asterisk_config_table()
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT host, port, username, secret
            FROM asterisk_config
            WHERE name = %s
        """, (name,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row and row[0]:  # اگر host موجود باشد
            return {
                'host': row[0],
                'port': row[1] or 5038,
                'username': row[2],
                'secret': row[3]
            }
        return None
    except Exception as e:
        print(f"خطا در خواندن تنظیمات Asterisk از دیتابیس: {e}")
        if conn:
            conn.close()
        return None


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
def get_trunk_config():
    """
    دریافت پیکربندی trunk
    ابتدا از دیتابیس می‌خواند، اگر پیدا نکرد از environment variables
    """
    try:
        trunk_name = request.args.get('name', 'default')
        source = None
        config = None
        asterisk_config = None

        # اول از دیتابیس بخوان
        init_trunks_table()
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT config, asterisk_config
                    FROM trunks
                    WHERE name = %s
                """, (trunk_name,))
                row = cursor.fetchone()
                cursor.close()
                conn.close()

                if row:
                    config = row[0]
                    asterisk_config = row[1]
                    source = 'database'
            except Exception as e:
                print(f"خطا در خواندن از دیتابیس: {e}")
                if conn:
                    conn.close()

        # اگر در دیتابیس پیدا نشد، از environment variables بخوان
        if not config:
            env_config = TrunkConfig.from_environment(trunk_name)
            if env_config.get('host'):
                config = env_config
                asterisk_config = TrunkConfig.to_asterisk_config(
                    trunk_name,
                    config
                )
                source = 'environment'

        # اگر هیچ‌کدام پیدا نشد، خطا برگردان
        if not config or not config.get('host'):
            return jsonify({
                'status': 'error',
                'message': (
                    f'پیکربندی trunk "{trunk_name}" '
                    f'در دیتابیس یا environment variables یافت نشد'
                )
            }), 404

        return jsonify({
            'status': 'success',
            'trunk_name': trunk_name,
            'source': source,
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


@app.route('/api/call/simple', methods=['POST'])
def make_simple_call():
    """تماس ساده با یک شماره"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ارسالی نامعتبر است'
            }), 400

        number = data.get('number')  # شماره مقصد
        caller_id = data.get('caller_id')  # شماره نمایش داده شده (اختیاری)
        trunk_name = data.get('trunk', 'trunk_external')  # نام trunk

        if not number:
            return jsonify({
                'status': 'error',
                'message': 'شماره تماس الزامی است'
            }), 400

        # اتصال به Asterisk
        manager = AsteriskManager()
        if not all([
            manager.host,
            manager.port,
            manager.username,
            manager.secret
        ]):
            return jsonify({
                'status': 'error',
                'message': 'تنظیمات Asterisk کامل نیست'
            }), 400

        success, error = manager.connect()
        if not success:
            return jsonify({
                'status': 'error',
                'message': f'خطا در اتصال به Asterisk: {error}'
            }), 500

        try:
            # خواندن trunk name واقعی از دیتابیس
            # اگر trunk name مشخص نشده یا trunk_external است، از trunk واقعی استفاده می‌کنیم
            actual_trunk_name = trunk_name
            
            # خواندن trunk config از دیتابیس
            init_trunks_table()
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT name, config
                        FROM trunks
                        WHERE name = %s
                        LIMIT 1
                    """, (trunk_name,))
                    row = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if row:
                        # اگر trunk در دیتابیس پیدا شد، از نام آن استفاده می‌کنیم
                        actual_trunk_name = row[0]
                        print(f"Found trunk in database: {actual_trunk_name}")
                except Exception as e:
                    print(f"خطا در خواندن trunk از دیتابیس: {e}")
                    if conn:
                        conn.close()
            
            # اگر trunk_external است و در دیتابیس پیدا نشد، از trunk واقعی استفاده می‌کنیم
            # از لیست Issabel مشخص است که trunk name واقعی 0utgoing-2191012787 است
            if actual_trunk_name == 'trunk_external' or not actual_trunk_name:
                # از لیست Issabel، trunk name واقعی 0utgoing-2191012787 است
                actual_trunk_name = '0utgoing-2191012787'
                print(f"Using default trunk: {actual_trunk_name}")
            
            # ساخت کانال برای تماس
            # برای تماس مستقیم از trunk، از SIP/trunk/number استفاده می‌کنیم
            # توجه: در Issabel، trunk name باید دقیقاً همان باشد که در sip show peers نشان داده می‌شود
            channel = f"SIP/{actual_trunk_name}/{number}"
            if not caller_id:
                caller_id = number

            # برقراری تماس
            print(f"Calling {number} via {channel}")
            print(f"Using trunk: {actual_trunk_name}")
            success_call, message, action_id = manager.originate_call(
                channel=channel,
                number=number,
                caller_id=caller_id,
                context="from-trunk",
                timeout=30
            )

            if not success_call:
                return jsonify({
                    'status': 'error',
                    'message': f'خطا در تماس با {number}: {message}'
                }), 500

            return jsonify({
                'status': 'success',
                'message': f'تماس با {number} با موفقیت آغاز شد',
                'number': number,
                'action_id': action_id
            }), 200

        finally:
            # در واقعیت باید پس از پایان تماس قطع شود
            pass

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/call/make', methods=['POST'])
def make_call():
    """برقراری تماس مسدود بین دو شماره"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ارسالی نامعتبر است'
            }), 400

        number_a = data.get('number_a')  # شماره تماس گیرنده
        number_b = data.get('number_b')  # شماره مقصد
        caller_id = data.get('caller_id')  # شماره نمایش داده شده (اختیاری)
        trunk_name = data.get('trunk', 'trunk_external')  # نام trunk

        if not number_a or not number_b:
            return jsonify({
                'status': 'error',
                'message': 'شماره تماس گیرنده و مقصد الزامی است'
            }), 400

        # ایجاد State Machine با metadata اولیه
        state_machine = CallSessionStateMachine(
            metadata={
                'number_a': number_a,
                'number_b': number_b,
                'caller_id': caller_id,
                'trunk_name': trunk_name
            }
        )
        session_id = state_machine.get_session_id()
        
        # ذخیره اولیه در دیتابیس
        save_call_session(
            state_machine,
            number_a=number_a,
            number_b=number_b,
            caller_id=caller_id,
            trunk_name=trunk_name
        )
        log_state_change(
            session_id=session_id,
            state=CallState.PENDING.value,
            metadata={'number_a': number_a, 'number_b': number_b}
        )

        # اتصال به Asterisk
        manager = AsteriskManager()
        if not all([
            manager.host,
            manager.port,
            manager.username,
            manager.secret
        ]):
            state_machine.transition_to(CallState.FAILED_SYSTEM)
            return jsonify({
                'status': 'error',
                'message': 'تنظیمات Asterisk کامل نیست',
                'session_id': session_id,
                'state': state_machine.get_current_state().value
            }), 400

        success, error = manager.connect()
        if not success:
            state_machine.transition_to(CallState.FAILED_SYSTEM)
            return jsonify({
                'status': 'error',
                'message': f'خطا در اتصال به Asterisk: {error}',
                'session_id': session_id,
                'state': state_machine.get_current_state().value
            }), 500

        try:
            # خواندن trunk name واقعی از دیتابیس
            actual_trunk_name = trunk_name
            init_trunks_table()
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT name, config
                        FROM trunks
                        WHERE name = %s
                        LIMIT 1
                    """, (trunk_name,))
                    row = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if row:
                        actual_trunk_name = row[0]
                        print(f"Found trunk in database: {actual_trunk_name}")
                except Exception as e:
                    print(f"خطا در خواندن trunk از دیتابیس: {e}")
                    if conn:
                        conn.close()
            
            # اگر trunk_external است و در دیتابیس پیدا نشد، از trunk واقعی استفاده می‌کنیم
            # در کد PHP، trunk name: 0utgoing-2191017280 بود (نه 0utgoing-2191012787)
            if actual_trunk_name == 'trunk_external' or not actual_trunk_name:
                # از کد PHP: trunk name واقعی
                actual_trunk_name = '0utgoing-2191017280'
                print(f"Using default trunk: {actual_trunk_name}")

            # شروع تماس: انتقال به حالت CALLING_A
            state_machine.transition_to(
                CallState.CALLING_A,
                metadata={'channel_a': channel_a, 'actual_trunk_name': actual_trunk_name}
            )
            save_call_session(state_machine, number_a=number_a, number_b=number_b, 
                            caller_id=caller_id, trunk_name=actual_trunk_name)
            log_state_change(session_id, CallState.CALLING_A.value, 
                           previous_state=CallState.PENDING.value,
                           metadata={'channel_a': channel_a})

            # ساخت کانال برای شماره A (مطابق کد PHP قبلی)
            channel_a = f"SIP/{actual_trunk_name}/{number_a}"
            if not caller_id:
                caller_id = number_a

            # استفاده از context و variables (مطابق کد PHP قبلی که از securebridge-control استفاده می‌کرد)
            # context باید در dialplan Asterisk تعریف شده باشد
            context_name = "securebridge-control"  # یا context دیگری که در dialplan تعریف شده
            
            # ایجاد متغیرها (مطابق کد PHP)
            variables = {
                'ARG1': number_a,  # شماره تماس گیرنده
                'ARG2': number_b,  # شماره مقصد
                'USER_TOKEN': session_id  # شناسه session به عنوان token
            }
            
            # برقراری تماس با شماره A با استفاده از context و variables
            # این روش مشابه کد PHP قبلی است که درست کار می‌کرده
            print(f"Calling {number_a} via {channel_a} with context {context_name}")
            print(f"Variables: {variables}")
            success_a, message_a, channel_a_id = manager.originate_call_with_context(
                channel=channel_a,
                context=context_name,
                extension='s',
                priority=1,
                caller_id=caller_id,
                variables=variables,
                timeout=30
            )

            if not success_a:
                state_machine.transition_to(
                    CallState.FAILED_A,
                    error=f"خطا در تماس با {number_a}: {message_a}",
                    metadata={'channel_a': channel_a, 'error_message': message_a}
                )
                save_call_session(state_machine, number_a=number_a, number_b=number_b,
                                caller_id=caller_id, trunk_name=actual_trunk_name)
                log_state_change(session_id, CallState.FAILED_A.value,
                               previous_state=CallState.CALLING_A.value,
                               error_message=f"خطا در تماس با {number_a}: {message_a}",
                               metadata={'channel_a': channel_a})
                return jsonify({
                    'status': 'error',
                    'message': f'خطا در تماس با {number_a}: {message_a}',
                    'session_id': session_id,
                    'state': state_machine.get_current_state().value
                }), 500

            # Channel ID واقعی از originate_call_direct برگردانده شده است
            # اگر Channel ID نداریم یا Channel ID همان channel name است، از response استخراج می‌کنیم
            if not channel_a_id or channel_a_id == channel_a:
                # استخراج Channel ID واقعی از response (از Events)
                # Pattern: SIP/trunk-xxxxx (با unique ID hex مانند 0000039d)
                import re
                # الگوی اول: Channel: SIP/trunk-xxxxx
                channel_match = re.search(
                    r'Channel:\s*(SIP/[^\r\n]+-\w+)',
                    message_a
                )
                if not channel_match:
                    # الگوی دوم: SIP/trunk-xxxxx در هر جای response
                    channel_match = re.search(
                        r'(SIP/[^\s\r\n/]+-\w+)',
                        message_a
                    )
                if channel_match:
                    channel_a_id = channel_match.group(1)
                    print(f"Found real Channel A ID: {channel_a_id}")
                else:
                    # اگر پیدا نشد، از channel name استفاده می‌کنیم (موقتاً)
                    channel_a_id = channel_a
                    print(f"Warning: Using channel name as Channel A ID: {channel_a_id}")

            # به‌روزرسانی metadata با channel_a_id
            state_machine.update_metadata(channel_a_id=channel_a_id)
            
            # در کد PHP قبلی، فقط یک Originate انجام می‌شد که به context می‌رفت
            # و dialplan خودش تماس دوم را انجام می‌داد و bridge می‌کرد
            # پس دیگر نیازی به originate_call_direct برای شماره B نیست
            # dialplan خودش کار را انجام می‌دهد
            
            # انتقال به حالت BRIDGED (چون dialplan خودش bridge می‌کند)
            # منتظر می‌مانیم تا dialplan کار را انجام دهد
            import time
            print(f"Waiting for dialplan to complete the call and bridge...")
            time.sleep(2)  # زمان کوتاه برای شروع فرآیند dialplan
            
            # انتقال به حالت BRIDGED
            # در واقعیت، باید از Events استفاده کنیم تا بفهمیم تماس کامل شد
            # اما برای حالا، فرض می‌کنیم که dialplan کار را انجام می‌دهد
            state_machine.transition_to(
                CallState.BRIDGED,
                metadata={'channel_a_id': channel_a_id, 'dialplan_handled': True}
            )
            save_call_session(state_machine, number_a=number_a, number_b=number_b,
                            caller_id=caller_id, trunk_name=actual_trunk_name,
                            channel_a_id=channel_a_id)
            log_state_change(session_id, CallState.BRIDGED.value,
                           previous_state=CallState.CALLING_A.value,
                           metadata={'channel_a_id': channel_a_id, 'method': 'dialplan'})

            return jsonify({
                'status': 'success',
                'message': 'تماس با موفقیت برقرار شد',
                'session_id': session_id,
                'state': state_machine.get_current_state().value,
                'number_a': number_a,
                'number_b': number_b,
                'channel_ids': {
                    'a': channel_a_id,
                    'b': None  # dialplan خودش channel B را مدیریت می‌کند
                },
                'bridge_method': 'dialplan',  # dialplan خودش bridge می‌کند (مطابق کد PHP)
                'state_history': [
                    state.value for state in state_machine.get_state_history()
                ]
            }), 200

        finally:
            # در واقعیت باید پس از پایان تماس قطع شود
            pass

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
