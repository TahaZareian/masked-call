import os
import uuid
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import Json
from typing import Optional, Dict
from datetime import datetime
from asterisk_manager import AsteriskManager
from call_state_machine import CallSessionStateMachine, CallState
from order_state_machine import OrderStateMachine, OrderState

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


# ==================== Database Schema ====================

def init_orders_table():
    """ایجاد جدول orders برای ذخیره سفارش‌های تماس (مشابه تراکنش در درگاه پرداخت)"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_id VARCHAR(255) UNIQUE NOT NULL,
                current_state VARCHAR(50) NOT NULL,
                user_token VARCHAR(255),
                number_a VARCHAR(50),
                number_b VARCHAR(50),
                caller_id VARCHAR(50),
                trunk_name VARCHAR(255),
                call_id VARCHAR(255),
                metadata JSONB,
                state_history JSONB,
                state_timestamps JSONB,
                error_log JSONB,
                is_final BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                failed_at TIMESTAMP,
                cancelled_at TIMESTAMP
            )
        """)
        
        # ایجاد ایندکس‌ها
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_order_id 
            ON orders(order_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_current_state 
            ON orders(current_state)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_user_token 
            ON orders(user_token)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_call_id 
            ON orders(call_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_created_at 
            ON orders(created_at)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول orders: {e}")
        if conn:
            conn.close()
        return False


def init_calls_table():
    """ایجاد جدول calls برای ذخیره تماس‌های واقعی (مشابه پرداخت در درگاه)"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id SERIAL PRIMARY KEY,
                call_id VARCHAR(255) UNIQUE NOT NULL,
                order_id VARCHAR(255),
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
                started_at TIMESTAMP,
                answered_at TIMESTAMP,
                bridged_at TIMESTAMP,
                completed_at TIMESTAMP,
                failed_at TIMESTAMP,
                duration_seconds INTEGER
            )
        """)
        
        # ایجاد ایندکس‌ها
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_call_id 
            ON calls(call_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_order_id 
            ON calls(order_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_current_state 
            ON calls(current_state)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_created_at 
            ON calls(created_at)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول calls: {e}")
        if conn:
            conn.close()
        return False


def init_events_table():
    """ایجاد جدول events برای Event-based tracking (مشابه webhook در درگاه پرداخت)"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR(255) UNIQUE NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                entity_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(255) NOT NULL,
                order_id VARCHAR(255),
                call_id VARCHAR(255),
                state VARCHAR(50),
                previous_state VARCHAR(50),
                metadata JSONB,
                error_message TEXT,
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # ایجاد ایندکس‌ها
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_event_id 
            ON events(event_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_entity 
            ON events(entity_type, entity_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_order_id 
            ON events(order_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_call_id 
            ON events(call_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_created_at 
            ON events(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_processed 
            ON events(processed)
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ایجاد جدول events: {e}")
        if conn:
            conn.close()
        return False


# ==================== Database Operations ====================

def save_order(order_state_machine: OrderStateMachine, **kwargs) -> bool:
    """ذخیره سفارش در دیتابیس"""
    init_orders_table()
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        state_data = order_state_machine.to_dict()
        
        # تعیین timestamp های خاص
        completed_at = None
        failed_at = None
        cancelled_at = None
        
        if order_state_machine.current_state == OrderState.COMPLETED:
            completed_at = datetime.now().isoformat()
        elif order_state_machine.current_state == OrderState.FAILED:
            failed_at = datetime.now().isoformat()
        elif order_state_machine.current_state == OrderState.CANCELLED:
            cancelled_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO orders (
                order_id, current_state, user_token, number_a, number_b,
                caller_id, trunk_name, call_id, metadata,
                state_history, state_timestamps, error_log, is_final,
                completed_at, failed_at, cancelled_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_id)
            DO UPDATE SET
                current_state = EXCLUDED.current_state,
                user_token = EXCLUDED.user_token,
                number_a = EXCLUDED.number_a,
                number_b = EXCLUDED.number_b,
                caller_id = EXCLUDED.caller_id,
                trunk_name = EXCLUDED.trunk_name,
                call_id = EXCLUDED.call_id,
                metadata = EXCLUDED.metadata,
                state_history = EXCLUDED.state_history,
                state_timestamps = EXCLUDED.state_timestamps,
                error_log = EXCLUDED.error_log,
                is_final = EXCLUDED.is_final,
                completed_at = EXCLUDED.completed_at,
                failed_at = EXCLUDED.failed_at,
                cancelled_at = EXCLUDED.cancelled_at,
                updated_at = CURRENT_TIMESTAMP
        """, (
            order_state_machine.order_id,
            order_state_machine.current_state.value,
            kwargs.get('user_token'),
            kwargs.get('number_a'),
            kwargs.get('number_b'),
            kwargs.get('caller_id'),
            kwargs.get('trunk_name'),
            order_state_machine.call_id,
            Json(order_state_machine.metadata),
            Json([s.value for s in order_state_machine.state_history]),
            Json(order_state_machine.state_timestamps),
            Json(order_state_machine.error_log),
            order_state_machine.is_final_state(),
            completed_at,
            failed_at,
            cancelled_at
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ذخیره order: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def save_call(call_state_machine: CallSessionStateMachine, order_id: str, **kwargs) -> bool:
    """ذخیره تماس واقعی در دیتابیس"""
    init_calls_table()
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        state_data = call_state_machine.to_dict()
        
        # تعیین timestamp های خاص
        started_at = None
        answered_at = None
        bridged_at = None
        completed_at = None
        failed_at = None
        duration = None
        
        # محاسبه duration
        if state_data['created_at'] and state_data['updated_at']:
            try:
                created = datetime.fromisoformat(state_data['created_at'])
                updated = datetime.fromisoformat(state_data['updated_at'])
                duration = int((updated - created).total_seconds())
            except Exception:
                duration = None
        
        # تعیین timestamp های خاص بر اساس state
        if call_state_machine.current_state == CallState.CALLING_A:
            started_at = datetime.now().isoformat()
        elif call_state_machine.current_state == CallState.CONNECTED_A:
            answered_at = datetime.now().isoformat()
        elif call_state_machine.current_state == CallState.BRIDGED:
            bridged_at = datetime.now().isoformat()
        elif call_state_machine.current_state == CallState.COMPLETED:
            completed_at = datetime.now().isoformat()
        elif call_state_machine.current_state in [CallState.FAILED_A, CallState.FAILED_B, CallState.FAILED_SYSTEM]:
            failed_at = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO calls (
                call_id, order_id, current_state, number_a, number_b,
                caller_id, trunk_name, channel_a_id, channel_b_id, metadata,
                state_history, state_timestamps, error_log, is_final,
                started_at, answered_at, bridged_at, completed_at, failed_at,
                duration_seconds
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (call_id)
            DO UPDATE SET
                order_id = EXCLUDED.order_id,
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
                started_at = EXCLUDED.started_at,
                answered_at = EXCLUDED.answered_at,
                bridged_at = EXCLUDED.bridged_at,
                completed_at = EXCLUDED.completed_at,
                failed_at = EXCLUDED.failed_at,
                duration_seconds = EXCLUDED.duration_seconds,
                updated_at = CURRENT_TIMESTAMP
        """, (
            call_state_machine.session_id,
            order_id,
            call_state_machine.current_state.value,
            kwargs.get('number_a'),
            kwargs.get('number_b'),
            kwargs.get('caller_id'),
            kwargs.get('trunk_name'),
            kwargs.get('channel_a_id'),
            kwargs.get('channel_b_id'),
            Json(call_state_machine.metadata),
            Json([s.value for s in call_state_machine.state_history]),
            Json(call_state_machine.state_timestamps),
            Json(call_state_machine.error_log),
            call_state_machine.is_final_state(),
            started_at,
            answered_at,
            bridged_at,
            completed_at,
            failed_at,
            duration
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"خطا در ذخیره call: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def create_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    order_id: Optional[str] = None,
    call_id: Optional[str] = None,
    state: Optional[str] = None,
    previous_state: Optional[str] = None,
    metadata: Optional[Dict] = None,
    error_message: Optional[str] = None
) -> bool:
    """ایجاد event (مشابه webhook در درگاه پرداخت)"""
    init_events_table()
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        event_id = str(uuid.uuid4())
        
        cursor.execute("""
            INSERT INTO events (
                event_id, event_type, entity_type, entity_id,
                order_id, call_id, state, previous_state,
                metadata, error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            event_id,
            event_type,
            entity_type,
            entity_id,
            order_id,
            call_id,
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
        print(f"خطا در ایجاد event: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False


def load_order(order_id: str) -> Optional[OrderStateMachine]:
    """بارگذاری سفارش از دیتابیس"""
    init_orders_table()
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT current_state, user_token, number_a, number_b, caller_id,
                   trunk_name, call_id, metadata, state_history, state_timestamps, error_log
            FROM orders
            WHERE order_id = %s
        """, (order_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return None
        
        # بازسازی order state machine
        order_state_machine = OrderStateMachine(
            initial_state=OrderState(row[0]),
            order_id=order_id,
            metadata=row[7] or {}
        )
        
        # بازسازی state history
        if row[8]:
            order_state_machine.state_history = [OrderState(s) for s in row[8]]
        
        # بازسازی timestamps و error log
        if row[9]:
            order_state_machine.state_timestamps = row[9]
        if row[10]:
            order_state_machine.error_log = row[10]
        
        # تنظیم call_id
        if row[6]:
            order_state_machine.set_call_id(row[6])
        
        return order_state_machine
    except Exception as e:
        print(f"خطا در بارگذاری order: {e}")
        if conn:
            conn.close()
        return None


def load_call(call_id: str) -> Optional[CallSessionStateMachine]:
    """بارگذاری تماس از دیتابیس"""
    init_calls_table()
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT current_state, metadata, state_history, state_timestamps, error_log
            FROM calls
            WHERE call_id = %s
        """, (call_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return None
        
        # بازسازی call state machine
        call_state_machine = CallSessionStateMachine(
            initial_state=CallState(row[0]),
            session_id=call_id,
            metadata=row[1] or {}
        )
        
        # بازسازی state history
        if row[2]:
            call_state_machine.state_history = [CallState(s) for s in row[2]]
        
        # بازسازی timestamps و error log
        if row[3]:
            call_state_machine.state_timestamps = row[3]
        if row[4]:
            call_state_machine.error_log = row[4]
        
        return call_state_machine
    except Exception as e:
        print(f"خطا در بارگذاری call: {e}")
        if conn:
            conn.close()
        return None


# ==================== API Endpoints ====================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'}), 200


@app.route('/api/order/create', methods=['POST'])
def create_order():
    """
    ایجاد سفارش تماس (مشابه ایجاد تراکنش در درگاه پرداخت)
    
    Body:
        {
            "from": "09140916320",
            "to": "09221609805",
            "user_token": "token123",
            "trunk": "0utgoing-2191017280" (optional)
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'اطلاعات ارسالی نامعتبر است'
            }), 400

        # پارامترها
        number_a = data.get('from') or data.get('number_a')
        number_b = data.get('to') or data.get('number_b')
        user_token = data.get('user_token')
        trunk_name = data.get('trunk', '0utgoing-2191017280')

        if not number_a or not number_b:
            return jsonify({
                'status': 'error',
                'message': 'پارامترهای from و to الزامی است'
            }), 400

        # ایجاد Order State Machine
        order_state_machine = OrderStateMachine(
            metadata={
                'number_a': number_a,
                'number_b': number_b,
                'user_token': user_token,
                'trunk_name': trunk_name
            }
        )
        order_id = order_state_machine.get_order_id()
        
        # انتقال به PENDING
        order_state_machine.transition_to(OrderState.PENDING)
        
        # ذخیره در دیتابیس
        save_order(
            order_state_machine,
            user_token=user_token,
            number_a=number_a,
            number_b=number_b,
            caller_id=number_a,
            trunk_name=trunk_name
        )
        
        # ایجاد event
        create_event(
            event_type='order.created',
            entity_type='order',
            entity_id=order_id,
            order_id=order_id,
            state=OrderState.PENDING.value,
            metadata={'number_a': number_a, 'number_b': number_b}
        )

        return jsonify({
            'status': 'success',
            'message': 'سفارش با موفقیت ایجاد شد',
            'order_id': order_id,
            'state': order_state_machine.current_state.value,
            'from': number_a,
            'to': number_b,
            'user_token': user_token
        }), 201

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/order/<order_id>/execute', methods=['POST'])
def execute_order(order_id: str):
    """
    اجرای سفارش تماس (مشابه پرداخت در درگاه)
    این endpoint سفارش را به حالت PROCESSING می‌برد و تماس را برقرار می‌کند
    """
    try:
        # بارگذاری order
        order_state_machine = load_order(order_id)
        if not order_state_machine:
            return jsonify({
                'status': 'error',
                'message': 'سفارش یافت نشد'
            }), 404

        if order_state_machine.is_final_state():
            return jsonify({
                'status': 'error',
                'message': 'این سفارش در حالت نهایی است و نمی‌تواند اجرا شود'
            }), 400

        # انتقال به PROCESSING
        order_state_machine.transition_to(OrderState.PROCESSING)
        save_order(order_state_machine)
        create_event(
            event_type='order.processing',
            entity_type='order',
            entity_id=order_id,
            order_id=order_id,
            state=OrderState.PROCESSING.value,
            previous_state=OrderState.PENDING.value
        )

        # دریافت اطلاعات از metadata
        metadata = order_state_machine.get_metadata()
        number_a = metadata.get('number_a')
        number_b = metadata.get('number_b')
        user_token = metadata.get('user_token')
        trunk_name = metadata.get('trunk_name', '0utgoing-2191017280')

        # اتصال به Asterisk
        manager = AsteriskManager()
        if not all([manager.host, manager.port, manager.username, manager.secret]):
            order_state_machine.transition_to(OrderState.FAILED, error='تنظیمات Asterisk کامل نیست')
            save_order(order_state_machine)
            return jsonify({
                'status': 'error',
                'message': 'تنظیمات Asterisk کامل نیست',
                'order_id': order_id,
                'state': order_state_machine.current_state.value
            }), 400

        success, error = manager.connect()
        if not success:
            order_state_machine.transition_to(OrderState.FAILED, error=f'خطا در اتصال به Asterisk: {error}')
            save_order(order_state_machine)
            return jsonify({
                'status': 'error',
                'message': f'خطا در اتصال به Asterisk: {error}',
                'order_id': order_id,
                'state': order_state_machine.current_state.value
            }), 500

        try:
            # ایجاد Call State Machine
            call_state_machine = CallSessionStateMachine(
                metadata={
                    'order_id': order_id,
                    'number_a': number_a,
                    'number_b': number_b,
                    'user_token': user_token,
                    'trunk_name': trunk_name
                }
            )
            call_id = call_state_machine.get_session_id()
            
            # انتقال order به INITIATED و ارتباط با call
            order_state_machine.set_call_id(call_id)
            order_state_machine.transition_to(OrderState.INITIATED)
            save_order(order_state_machine)
            create_event(
                event_type='order.initiated',
                entity_type='order',
                entity_id=order_id,
                order_id=order_id,
                call_id=call_id,
                state=OrderState.INITIATED.value,
                previous_state=OrderState.PROCESSING.value
            )

            # ساخت کانال و برقراری تماس
            channel = f"SIP/{trunk_name}/{number_a}"
            
            # انتقال call به CALLING_A
            call_state_machine.transition_to(
                CallState.CALLING_A,
                metadata={'channel': channel, 'trunk_name': trunk_name}
            )
            save_call(call_state_machine, order_id=order_id,
                     number_a=number_a, number_b=number_b,
                     caller_id=number_a, trunk_name=trunk_name)
            
            create_event(
                event_type='call.calling_a',
                entity_type='call',
                entity_id=call_id,
                order_id=order_id,
                call_id=call_id,
                state=CallState.CALLING_A.value,
                previous_state=CallState.PENDING.value,
                metadata={'channel': channel}
            )

            # استفاده از context و variables (مطابق کد PHP)
            context_name = "securebridge-control"
            variables = {
                'ARG1': str(number_a),
                'ARG2': str(number_b),
                'USER_TOKEN': str(user_token or order_id)
            }
            
            # برقراری تماس
            print(f"Calling {number_a} via {channel} with context {context_name}")
            print(f"Variables: {variables}")
            success_call, message, channel_id = manager.originate_call_with_context(
                channel=channel,
                context=context_name,
                extension='s',
                priority=1,
                caller_id=number_a,
                variables=variables,
                timeout=30
            )

            if not success_call:
                call_state_machine.transition_to(
                    CallState.FAILED_A,
                    error=f"خطا در برقراری تماس: {message}",
                    metadata={'channel': channel, 'error_message': message}
                )
                save_call(call_state_machine, order_id=order_id,
                         number_a=number_a, number_b=number_b,
                         caller_id=number_a, trunk_name=trunk_name)
                
                order_state_machine.transition_to(OrderState.FAILED, error=f"خطا در برقراری تماس: {message}")
                save_order(order_state_machine)
                
                create_event(
                    event_type='call.failed',
                    entity_type='call',
                    entity_id=call_id,
                    order_id=order_id,
                    call_id=call_id,
                    state=CallState.FAILED_A.value,
                    error_message=f"خطا در برقراری تماس: {message}"
                )
                
                return jsonify({
                    'status': 'error',
                    'message': f'خطا در برقراری تماس: {message}',
                    'order_id': order_id,
                    'call_id': call_id,
                    'state': order_state_machine.current_state.value
                }), 500

            # استخراج Channel ID (اگر وجود دارد)
            if channel_id and channel_id != channel:
                call_state_machine.update_metadata(channel_id=channel_id)
            
            # انتقال call به BRIDGED (چون dialplan خودش bridge می‌کند)
            call_state_machine.transition_to(
                CallState.BRIDGED,
                metadata={'channel_id': channel_id or channel, 'dialplan_handled': True}
            )
            save_call(call_state_machine, order_id=order_id,
                     number_a=number_a, number_b=number_b,
                     caller_id=number_a, trunk_name=trunk_name,
                     channel_a_id=channel_id or channel)
            
            create_event(
                event_type='call.bridged',
                entity_type='call',
                entity_id=call_id,
                order_id=order_id,
                call_id=call_id,
                state=CallState.BRIDGED.value,
                previous_state=CallState.CALLING_A.value,
                metadata={'channel_id': channel_id or channel, 'method': 'dialplan'}
            )

            # انتقال order به VERIFIED
            order_state_machine.transition_to(OrderState.VERIFIED)
            save_order(order_state_machine)
            create_event(
                event_type='order.verified',
                entity_type='order',
                entity_id=order_id,
                order_id=order_id,
                call_id=call_id,
                state=OrderState.VERIFIED.value,
                previous_state=OrderState.INITIATED.value
            )

            return jsonify({
                'status': 'success',
                'message': 'تماس با موفقیت برقرار شد',
                'order_id': order_id,
                'call_id': call_id,
                'state': order_state_machine.current_state.value,
                'call_state': call_state_machine.current_state.value,
                'from': number_a,
                'to': number_b,
                'user_token': user_token or order_id
            }), 200

        finally:
            manager.disconnect()

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/order/<order_id>/status', methods=['GET'])
def get_order_status(order_id: str):
    """
    بررسی وضعیت سفارش (مشابه بررسی وضعیت تراکنش در درگاه پرداخت)
    """
    try:
        order_state_machine = load_order(order_id)
        if not order_state_machine:
            return jsonify({
                'status': 'error',
                'message': 'سفارش یافت نشد'
            }), 404

        # بارگذاری call مرتبط (اگر وجود دارد)
        call_info = None
        if order_state_machine.call_id:
            call_state_machine = load_call(order_state_machine.call_id)
            if call_state_machine:
                call_info = {
                    'call_id': call_state_machine.session_id,
                    'state': call_state_machine.current_state.value,
                    'is_final': call_state_machine.is_final_state(),
                    'state_history': [s.value for s in call_state_machine.state_history],
                    'last_updated': call_state_machine.state_timestamps[-1]['timestamp'] if call_state_machine.state_timestamps else None
                }

        return jsonify({
            'status': 'success',
            'order': {
                'order_id': order_state_machine.order_id,
                'state': order_state_machine.current_state.value,
                'is_final': order_state_machine.is_final_state(),
                'state_history': [s.value for s in order_state_machine.state_history],
                'state_timestamps': order_state_machine.state_timestamps,
                'error_log': order_state_machine.error_log,
                'metadata': order_state_machine.metadata,
                'call_id': order_state_machine.call_id,
                'call': call_info
            }
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/call/<call_id>/status', methods=['GET'])
def get_call_status(call_id: str):
    """
    بررسی وضعیت تماس (مشابه بررسی جزئیات پرداخت)
    """
    try:
        call_state_machine = load_call(call_id)
        if not call_state_machine:
            return jsonify({
                'status': 'error',
                'message': 'تماس یافت نشد'
            }), 404

        return jsonify({
            'status': 'success',
            'call': {
                'call_id': call_state_machine.session_id,
                'state': call_state_machine.current_state.value,
                'is_final': call_state_machine.is_final_state(),
                'state_history': [s.value for s in call_state_machine.state_history],
                'state_timestamps': call_state_machine.state_timestamps,
                'error_log': call_state_machine.error_log,
                'metadata': call_state_machine.metadata
            }
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


@app.route('/api/order/<order_id>/events', methods=['GET'])
def get_order_events(order_id: str):
    """
    دریافت events مرتبط با سفارش (مشابه webhook events در درگاه پرداخت)
    """
    try:
        init_events_table()
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'status': 'error',
                'message': 'خطا در اتصال به دیتابیس'
            }), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT event_id, event_type, entity_type, entity_id,
                   call_id, state, previous_state, metadata, error_message,
                   processed, created_at
            FROM events
            WHERE order_id = %s
            ORDER BY created_at ASC
        """, (order_id,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        events = []
        for row in rows:
            events.append({
                'event_id': row[0],
                'event_type': row[1],
                'entity_type': row[2],
                'entity_id': row[3],
                'call_id': row[4],
                'state': row[5],
                'previous_state': row[6],
                'metadata': row[7],
                'error_message': row[8],
                'processed': row[9],
                'created_at': row[10].isoformat() if row[10] else None
            })

        return jsonify({
            'status': 'success',
            'order_id': order_id,
            'events': events,
            'total': len(events)
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
