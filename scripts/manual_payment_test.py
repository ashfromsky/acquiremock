import requests
import json
import webbrowser
from datetime import datetime
import random
import pytest

API_URL = "http://localhost:8000"
WEBHOOK_URL = "https://webhook.site/unique-id"
REDIRECT_URL = "http://localhost:8000"

def test_create_invoice():
    print("🧪 Тестування AcquireMock Payment Gateway\n")
    print("=" * 50)

    rand_amount = random.randint(100, 1000)

    payload = {
        "amount": rand_amount,
        "reference": f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "webhook_url": WEBHOOK_URL,
        "redirect_url": REDIRECT_URL
    }

    print("\n📤 Відправляю запит на створення invoice...")
    print(f"URL: {API_URL}/api/create-invoice")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(
            f"{API_URL}/api/create-invoice",
            json=payload,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        print("✅ Invoice успішно створено!")
        print(f"\n📋 Відповідь сервера:")
        print(json.dumps(data, indent=2))

        page_url = data.get("pageUrl")

        if page_url:
            print(f"\n🔗 URL сторінки оплати:")
            print(page_url)

            print("\n" + "=" * 50)
            choice = input("Відкрити сторінку оплати в браузері? (y/n): ")

            if choice.lower() == 'y':
                print("\n🌐 Відкриваю браузер...")
                webbrowser.open(page_url)

                print("\n💡 Підказки для тестування:")
                print("   ✓ Для успішної оплати: 4444 4444 4444 4444")
                print("   ✓ Термін дії: будь-який (наприклад, 12/25)")
                print("   ✓ CVV: будь-який (наприклад, 123)")
                print("   ✓ Інші картки викличуть помилку 'Insufficient funds'")

                print(f"\n🔔 Webhook буде відправлено на:")
                print(f"   {WEBHOOK_URL}")
                print("   Відкрийте цей URL щоб побачити webhook дані")
            else:
                print("\n👋 Скопіюйте URL вище та відкрийте вручну")

    except requests.exceptions.ConnectionError:
        print("❌ Помилка: Не можу підключитися до сервера")
        print("   Перевірте чи запущений FastAPI на http://localhost:8000")
        print("   Запустіть: uvicorn main:app --port 8000 --reload")

    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Помилка: {e}")
        try:
            print(f"Статус код: {response.status_code}")
            print(f"Відповідь: {response.text}")
        except:
            pass

    except Exception as e:
        print(f"❌ Несподівана помилка: {e}")


def test_health_check():
    print("\n🏥 Перевірка доступності сервера...")

    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        data = response.json()

        print("✅ Сервер працює!")
        assert data.get('status') == 'ok'
        assert 'timestamp' in data

    except Exception as e:
        pytest.fail(f"❌ Сервер не відповідає: {e}")


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════╗
    ║   AcquireMock Payment Gateway Test   ║
    ╚═══════════════════════════════════════╝
    """)

    if test_health_check():
        test_create_invoice()
    else:
        print("\n💡 Запустіть FastAPI сервер:")
        print("   uvicorn main:app --port 8000 --reload")

    print("\n" + "=" * 50)
    print("Тестування завершено\n")