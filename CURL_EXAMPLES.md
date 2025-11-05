# دستورات cURL برای تست API

## 1. Health Check

```bash
curl -X GET http://localhost:5000/health
```

## 2. ایجاد سفارش تماس (Order)

```bash
curl -X POST http://localhost:5000/api/order/create \
  -H "Content-Type: application/json" \
  -d '{
    "from": "09140916320",
    "to": "09221609805",
    "user_token": "test_token_123",
    "trunk": "0utgoing-2191017280"
  }'
```

یا بدون trunk (پیش‌فرض استفاده می‌شود):

```bash
curl -X POST http://localhost:5000/api/order/create \
  -H "Content-Type: application/json" \
  -d '{
    "from": "09140916320",
    "to": "09221609805",
    "user_token": "test_token_123"
  }'
```

**پاسخ موفق:**
```json
{
  "status": "success",
  "message": "سفارش با موفقیت ایجاد شد",
  "order_id": "uuid-here",
  "state": "pending",
  "from": "09140916320",
  "to": "09221609805",
  "user_token": "test_token_123"
}
```

## 3. اجرای سفارش (برقراری تماس)

```bash
# جایگزین کنید <order_id> با order_id دریافتی از مرحله قبل
curl -X POST http://localhost:5000/api/order/<order_id>/execute \
  -H "Content-Type: application/json"
```

**مثال:**
```bash
curl -X POST http://localhost:5000/api/order/123e4567-e89b-12d3-a456-426614174000/execute \
  -H "Content-Type: application/json"
```

**پاسخ موفق:**
```json
{
  "status": "success",
  "message": "تماس با موفقیت برقرار شد",
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "call_id": "call-uuid-here",
  "state": "verified",
  "call_state": "bridged",
  "from": "09140916320",
  "to": "09221609805",
  "user_token": "test_token_123"
}
```

## 4. بررسی وضعیت سفارش (Order Status)

```bash
curl -X GET http://localhost:5000/api/order/<order_id>/status
```

**مثال:**
```bash
curl -X GET http://localhost:5000/api/order/123e4567-e89b-12d3-a456-426614174000/status
```

**پاسخ:**
```json
{
  "status": "success",
  "order": {
    "order_id": "123e4567-e89b-12d3-a456-426614174000",
    "state": "verified",
    "is_final": false,
    "state_history": ["created", "pending", "processing", "initiated", "verified"],
    "state_timestamps": [
      {
        "state": "created",
        "timestamp": "2024-01-01T10:00:00",
        "metadata": {}
      },
      {
        "state": "pending",
        "previous_state": "created",
        "timestamp": "2024-01-01T10:00:01",
        "metadata": {}
      }
    ],
    "error_log": [],
    "metadata": {
      "number_a": "09140916320",
      "number_b": "09221609805",
      "user_token": "test_token_123",
      "trunk_name": "0utgoing-2191017280"
    },
    "call_id": "call-uuid-here",
    "call": {
      "call_id": "call-uuid-here",
      "state": "bridged",
      "is_final": false,
      "state_history": ["pending", "calling_a", "bridged"],
      "last_updated": "2024-01-01T10:00:05"
    }
  }
}
```

## 5. بررسی وضعیت تماس (Call Status)

```bash
curl -X GET http://localhost:5000/api/call/<call_id>/status
```

**مثال:**
```bash
curl -X GET http://localhost:5000/api/call/call-uuid-here/status
```

**پاسخ:**
```json
{
  "status": "success",
  "call": {
    "call_id": "call-uuid-here",
    "state": "bridged",
    "is_final": false,
    "state_history": ["pending", "calling_a", "bridged"],
    "state_timestamps": [
      {
        "state": "pending",
        "timestamp": "2024-01-01T10:00:00",
        "metadata": {}
      },
      {
        "state": "calling_a",
        "previous_state": "pending",
        "timestamp": "2024-01-01T10:00:02",
        "metadata": {
          "channel": "SIP/0utgoing-2191017280/09140916320"
        }
      }
    ],
    "error_log": [],
    "metadata": {
      "order_id": "123e4567-e89b-12d3-a456-426614174000",
      "number_a": "09140916320",
      "number_b": "09221609805"
    }
  }
}
```

## 6. دریافت Events مرتبط با سفارش

```bash
curl -X GET http://localhost:5000/api/order/<order_id>/events
```

**مثال:**
```bash
curl -X GET http://localhost:5000/api/order/123e4567-e89b-12d3-a456-426614174000/events
```

**پاسخ:**
```json
{
  "status": "success",
  "order_id": "123e4567-e89b-12d3-a456-426614174000",
  "events": [
    {
      "event_id": "event-uuid-1",
      "event_type": "order.created",
      "entity_type": "order",
      "entity_id": "123e4567-e89b-12d3-a456-426614174000",
      "call_id": null,
      "state": "pending",
      "previous_state": null,
      "metadata": {
        "number_a": "09140916320",
        "number_b": "09221609805"
      },
      "error_message": null,
      "processed": false,
      "created_at": "2024-01-01T10:00:01"
    },
    {
      "event_id": "event-uuid-2",
      "event_type": "order.processing",
      "entity_type": "order",
      "entity_id": "123e4567-e89b-12d3-a456-426614174000",
      "call_id": null,
      "state": "processing",
      "previous_state": "pending",
      "metadata": {},
      "error_message": null,
      "processed": false,
      "created_at": "2024-01-01T10:00:02"
    },
    {
      "event_id": "event-uuid-3",
      "event_type": "call.bridged",
      "entity_type": "call",
      "entity_id": "call-uuid-here",
      "call_id": "call-uuid-here",
      "state": "bridged",
      "previous_state": "calling_a",
      "metadata": {
        "channel_id": "SIP/0utgoing-2191017280-0000039d",
        "method": "dialplan"
      },
      "error_message": null,
      "processed": false,
      "created_at": "2024-01-01T10:00:05"
    }
  ],
  "total": 3
}
```

## 7. مثال کامل - از ایجاد تا اجرا

```bash
# 1. ایجاد سفارش
ORDER_RESPONSE=$(curl -s -X POST http://localhost:5000/api/order/create \
  -H "Content-Type: application/json" \
  -d '{
    "from": "09140916320",
    "to": "09221609805",
    "user_token": "test_token_123"
  }')

echo "Order Response: $ORDER_RESPONSE"

# 2. استخراج order_id (نیاز به jq یا parse کردن JSON)
ORDER_ID=$(echo $ORDER_RESPONSE | grep -o '"order_id":"[^"]*' | cut -d'"' -f4)
echo "Order ID: $ORDER_ID"

# 3. اجرای سفارش
EXECUTE_RESPONSE=$(curl -s -X POST http://localhost:5000/api/order/$ORDER_ID/execute \
  -H "Content-Type: application/json")

echo "Execute Response: $EXECUTE_RESPONSE"

# 4. بررسی وضعیت (چند بار)
for i in {1..5}; do
  echo "Checking status (attempt $i)..."
  curl -s -X GET http://localhost:5000/api/order/$ORDER_ID/status | jq .
  sleep 2
done

# 5. دریافت Events
curl -s -X GET http://localhost:5000/api/order/$ORDER_ID/events | jq .
```

## 8. مثال با PowerShell (Windows)

```powershell
# 1. ایجاد سفارش
$orderBody = @{
    from = "09140916320"
    to = "09221609805"
    user_token = "test_token_123"
} | ConvertTo-Json

$orderResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/order/create" `
    -Method POST `
    -ContentType "application/json" `
    -Body $orderBody

Write-Host "Order ID: $($orderResponse.order_id)"

# 2. اجرای سفارش
$executeResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/order/$($orderResponse.order_id)/execute" `
    -Method POST `
    -ContentType "application/json"

Write-Host "Call ID: $($executeResponse.call_id)"

# 3. بررسی وضعیت
$statusResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/order/$($orderResponse.order_id)/status" `
    -Method GET

Write-Host "Order State: $($statusResponse.order.state)"

# 4. دریافت Events
$eventsResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/order/$($orderResponse.order_id)/events" `
    -Method GET

Write-Host "Total Events: $($eventsResponse.total)"
```

## 9. مثال با Python (requests)

```python
import requests
import time
import json

BASE_URL = "http://localhost:5000"

# 1. ایجاد سفارش
order_data = {
    "from": "09140916320",
    "to": "09221609805",
    "user_token": "test_token_123"
}

response = requests.post(f"{BASE_URL}/api/order/create", json=order_data)
order = response.json()
print(f"Order ID: {order['order_id']}")

# 2. اجرای سفارش
order_id = order['order_id']
response = requests.post(f"{BASE_URL}/api/order/{order_id}/execute")
execute = response.json()
print(f"Call ID: {execute['call_id']}")

# 3. بررسی وضعیت (polling)
for i in range(5):
    response = requests.get(f"{BASE_URL}/api/order/{order_id}/status")
    status = response.json()
    print(f"Order State: {status['order']['state']}")
    print(f"Call State: {status['order']['call']['state'] if status['order']['call'] else 'N/A'}")
    time.sleep(2)

# 4. دریافت Events
response = requests.get(f"{BASE_URL}/api/order/{order_id}/events")
events = response.json()
print(f"Total Events: {events['total']}")
for event in events['events']:
    print(f"  - {event['event_type']}: {event['state']}")
```

## نکات مهم

1. **Base URL**: اگر API روی سرور دیگری اجرا می‌شود، `localhost:5000` را با آدرس واقعی جایگزین کنید.

2. **Order ID و Call ID**: این ID ها را از پاسخ‌های API دریافت می‌کنید و باید در مراحل بعدی استفاده کنید.

3. **Polling**: برای بررسی وضعیت، می‌توانید هر چند ثانیه یکبار status را چک کنید.

4. **Error Handling**: در صورت خطا، API پاسخ‌های مناسب با کدهای HTTP برمی‌گرداند:
   - `200`: موفق
   - `201`: ایجاد شد
   - `400`: خطای درخواست
   - `404`: پیدا نشد
   - `500`: خطای سرور

5. **jq**: برای parse کردن JSON در bash، می‌توانید از `jq` استفاده کنید:
   ```bash
   apt-get install jq  # یا brew install jq
   ```

