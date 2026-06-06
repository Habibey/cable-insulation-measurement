# Hafif ve güncel bir Python imajı seçiyoruz
FROM python:3.11-slim

# OpenCV'nin Linux ortamında sorunsuz çalışması için gerekli sistem bağımlılıklarını kuruyoruz
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizinini tanımlıyoruz
WORKDIR /app

# Bağımlılıkları kopyalayıp cache mekanizmasını efektif kullanarak kuruyoruz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm proje dosyalarını konteyner içine kopyalıyoruz
COPY . .

# FastAPI'nin çalışacağı portu dışarı açıyoruz
EXPOSE 8000

# Uygulamayı uvicorn üzerinden ayağa kaldırıyoruz
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]