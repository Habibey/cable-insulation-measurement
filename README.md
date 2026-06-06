# Cable Insulation Measurement

OpenCV ve FastAPI kullanılarak geliştirilen kablo izolasyon kalınlığı ölçüm prototipidir.

## Amaç

Bu proje, kablo kesit görüntülerinden temel geometrik ölçümler çıkarmayı hedefler. Sistem; dış çap, iç çap, izolasyon kalınlığı, minimum/maksimum/ortalama kalınlık ve eksen kaçıklığı gibi değerleri hesaplar.

## Özellikler

- Kablo kesit görüntüsü yükleme
- Kablo tipi, kesit ID, tarih ve pixel-mm katsayısı girişi
- OpenCV ile dış sınır tespiti
- İç bölge sınırı tespiti veya fallback yaklaşımı
- Dış çap ve iç çap hesaplama
- Farklı açılarda izolasyon kalınlığı ölçümü
- Minimum, maksimum ve ortalama kalınlık hesabı
- Eksen kaçıklığı hesabı
- Sonuç görseli, tablo ve JSON çıktısı

## Kullanılan Teknolojiler

- Python
- FastAPI
- OpenCV
- NumPy
- HTML
- CSS
- JavaScript
- Docker

## Kurulum

```bash
pip install -r requirements.txts