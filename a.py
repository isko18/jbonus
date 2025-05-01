import serial
import threading
import time

# Указываем только нужные порты
port_list = ['COM9', 'COM11']

def open_safe_port(port, baud=9600):
    try:
        ser = serial.Serial(port, baud, timeout=1)
        print(f"✅ Открыт порт: {port}")
        return ser
    except Exception as e:
        print(f"❌ Не удалось открыть порт {port}: {e}")
        return None

all_serials = []
for p in port_list:
    ser = open_safe_port(p)
    if ser is not None:
        all_serials.append((ser, p))

if len(all_serials) != 2:
    print("❌ Не удалось открыть оба нужных порта! Проверь COM9 и COM11.")
    exit(1)

ser1, name1 = all_serials[0]  # Например, датчик
ser2, name2 = all_serials[1]  # Второй Arduino
time.sleep(2)  # ждём подключения Arduino

def listen_port1_forward_to_2():
    while True:
        try:
            line = ser1.readline().decode(errors='ignore').strip()
            if line:
                print(f"📩 [{name1}] Принято: {line}")
                # Любая команда, пришедшая от датчика, сразу уходит на второй Arduino:
                ser2.write((line + '\n').encode())
                print(f"⏩ [{name1}] Переслал команду '{line}' на [{name2}]")
        except Exception as e:
            print(f"[{name1}] Ошибка чтения: {e}")

def listen_port2_print():
    while True:
        try:
            line = ser2.readline().decode(errors='ignore').strip()
            if line:
                print(f"📩 [{name2}] Принято: {line}")
        except Exception as e:
            print(f"[{name2}] Ошибка чтения: {e}")

# Запуск прослушивания обоих портов
t1 = threading.Thread(target=listen_port1_forward_to_2, daemon=True)
t2 = threading.Thread(target=listen_port2_print, daemon=True)
t1.start()
t2.start()

print("\n🟢 Готово! Формат: 1 команда, 2 команда, all команда, exit")
print(f"1: {name1}    2: {name2}")

try:
    while True:
        cmd = input("👉 [порт] [команда] или 'exit': ").strip()
        if cmd == "exit":
            print("🚪 Выход...")
            break

        parts = cmd.split(maxsplit=1)
        if len(parts) == 2:
            target, command = parts
            if target == "all":
                ser1.write((command + '\n').encode())
                ser2.write((command + '\n').encode())
                print(f"🔁 [all] Отправлено: {command}")
            elif target == "1":
                ser1.write((command + '\n').encode())
                print(f"🔁 [{name1}] Отправлено: {command}")
            elif target == "2":
                ser2.write((command + '\n').encode())
                print(f"🔁 [{name2}] Отправлено: {command}")
            else:
                print(f"⚠️ Неизвестный порт! Используй 'all', '1' или '2'.")
        else:
            print("⚠️ Формат: [порт] [команда]. Пример: all PUSH, 1 f, 2 OPEN, exit")

finally:
    ser1.close()
    ser2.close()
    print("Порты закрыты.")
