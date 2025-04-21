import qrcode
import os

def generate_qr(fandomat_token, filename="resources/fandomat_qr.png"):
    # ✅ Создаём папку, если нет
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    qr_data = fandomat_token  # 🔥 Только сам токен
    qr = qrcode.make(qr_data)
    qr.save(filename)
    return filename
