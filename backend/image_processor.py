import cv2
import numpy as np
import os
import uuid
from typing import Dict, Any


def _distance(p1, p2):
    """
    İki nokta arasındaki Öklid mesafesini hesaplar.
    Bu fonksiyon hem eksen kaçıklığı hem de kalınlık ölçümü için kullanılır.
    """
    return float(
        np.sqrt(
            (p1[0] - p2[0]) ** 2 +
            (p1[1] - p2[1]) ** 2
        )
    )


def _get_ellipse_info(contour):
    """
    Verilen konturdan yaklaşık merkez ve çap bilgisi çıkarır.

    Eğer konturda en az 5 nokta varsa OpenCV fitEllipse kullanılır.
    fitEllipse, kontura en uygun elipsi yerleştirir.

    Eğer kontur 5 noktadan küçükse fallback olarak boundingRect kullanılır.
    """

    if len(contour) >= 5:
        ellipse = cv2.fitEllipse(contour)

        # fitEllipse çıktısı:
        # merkez, eksen uzunlukları, açı
        (cx, cy), (axis1, axis2), angle = ellipse

        # Kablo kesiti tam daire olmayabilir.
        # Bu yüzden iki eksenin ortalaması yaklaşık çap olarak alınır.
        diameter = float((axis1 + axis2) / 2.0)

        return {
            "center": (float(cx), float(cy)),
            "diameter": diameter,
            "ellipse": ellipse
        }

    # fitEllipse kullanılamazsa dikdörtgen yaklaşımı yapılır.
    x, y, w, h = cv2.boundingRect(contour)

    return {
        "center": (float(x + w / 2), float(y + h / 2)),
        "diameter": float((w + h) / 2),
        "ellipse": None
    }


def _point_on_circle(center, radius, angle_rad):
    """
    Verilen merkez, yarıçap ve açıya göre çember üzerinde bir nokta hesaplar.

    Bu fonksiyon açısal izolasyon kalınlığı ölçümlerinde kullanılır.
    Örneğin 6 ölçüm için 0, 60, 120, 180, 240, 300 derece noktaları hesaplanır.
    """

    x = center[0] + radius * np.cos(angle_rad)
    y = center[1] + radius * np.sin(angle_rad)

    return (int(round(x)), int(round(y)))


def _read_image_safe(image_path: str):
    """
    Görüntüyü güvenli şekilde okur.

    Normalde cv2.imread yeterlidir.
    Ancak Windows ortamında Türkçe karakter, boşluk veya özel karakterli dosya yollarında
    cv2.imread bazen None döndürebilir.

    Bu durumda np.fromfile + cv2.imdecode fallback olarak kullanılır.
    """

    image = cv2.imread(image_path)

    if image is None:
        file_bytes = np.fromfile(image_path, dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    return image


def process_cable_image(
    image_path: str,
    image_name: str,
    cable_type: str,
    section_id: str,
    section_date: str,
    pixel_to_mm: float,
    measurement_count: int = 6
) -> Dict[str, Any]:
    """
    Ana görüntü işleme fonksiyonu.

    Bu fonksiyon:
    - görüntüyü okur
    - dış sınırı bulur
    - iç sınırı bulmaya çalışır
    - dış/iç merkez ve çap hesaplar
    - farklı açılardan izolasyon kalınlığı ölçer
    - eksen kaçıklığını hesaplar
    - açıklamalı sonuç görseli üretir
    - sonuçları JSON uyumlu dictionary olarak döndürür
    """

    # ------------------------------------------------------------
    # 1. Görüntüyü oku
    # ------------------------------------------------------------
    image = _read_image_safe(image_path)

    if image is None:
        raise ValueError(f"Görüntü okunamadı. Dosya yolu: {image_path}")

    # Sonuç çizimlerini orijinal görüntü üzerine yapabilmek için kopya alıyoruz.
    original = image.copy()

    # ------------------------------------------------------------
    # 2. Ön işleme: griye çevirme ve gürültü azaltma
    # ------------------------------------------------------------
# Görüntünün renkli mi siyah-beyaz mı olduğunu anlamak için doygunluk (Saturation) kontrolü
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    s_channel = hsv[:,:,1]
    
    # Eğer ortalama doygunluk çok düşükse (örneğin < 15), bu siyah-beyaz bir görüntüdür
    if np.mean(s_channel) < 15:
        # SİYAH-BEYAZ GÖRÜNTÜ İÇİN GRİ TONLAMA MANTIĞI
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        _, thresh = cv2.threshold(
            blur,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
    else:
        # RENKLİ GÖRÜNTÜ İÇİN HSV MANTIĞI
        blur = cv2.GaussianBlur(s_channel, (7, 7), 0)
        _, thresh = cv2.threshold(
            blur,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    # ------------------------------------------------------------
    # 4. Morfolojik işlemler ile maskeyi temizleme
    # ------------------------------------------------------------
    kernel = np.ones((5, 5), np.uint8)

    # Opening: küçük gürültüleri temizler.
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # Closing: küçük boşlukları kapatır.
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # ------------------------------------------------------------
    # 5. Dış konturu bulma
    # ------------------------------------------------------------
    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if len(contours) == 0:
        raise ValueError("Dış kontur bulunamadı.")

    # En büyük kontur dış kablo sınırı olarak kabul edilir.
    outer_contour = max(contours, key=cv2.contourArea)
    outer_area = cv2.contourArea(outer_contour)

    # Dış konturdan merkez ve çap bilgisi çıkarılır.
    outer_info = _get_ellipse_info(outer_contour)

    # ------------------------------------------------------------
    # 6. İç kontur adaylarını bulma
    # ------------------------------------------------------------
    # İç bölge genelde açık/beyaz olduğu için threshold maskesini ters çeviriyoruz.
    inner_thresh = cv2.bitwise_not(thresh)

    # RETR_LIST tüm konturları döndürür.
    # Böylece iç bölge veya çoklu damar konturları yakalanabilir.
    inner_contours, _ = cv2.findContours(
        inner_thresh,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE
    )

    image_area = image.shape[0] * image.shape[1]
    candidate_inner_contours = []

    for contour in inner_contours:
        area = cv2.contourArea(contour)

        # Çok küçük alanlar genelde gürültüdür.
        if area < 100:
            continue

        # Görüntünün çok büyük kısmını kaplayan alanlar genelde arka plandır.
        if area > image_area * 0.90:
            continue

        # İç alan dış konturdan büyük olamaz.
        if area >= outer_area:
            continue

        # Kontur merkezi moment ile hesaplanır.
        M = cv2.moments(contour)

        if M["m00"] == 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # Aday iç konturun merkezi dış konturun içinde olmalıdır.
        inside = cv2.pointPolygonTest(outer_contour, (cx, cy), False)

        if inside >= 0:
            candidate_inner_contours.append(contour)

    # ------------------------------------------------------------
    # 7. İç bölge bilgisini belirleme
    # ------------------------------------------------------------
    warning = None
    inner_contours_to_draw = []

    if len(candidate_inner_contours) == 0:
        # İç kontur bulunamazsa sistem tamamen hata vermesin diye fallback kullanılır.
        # Bu durumda iç merkez dış merkez ile aynı kabul edilir.
        # Kullanıcıya uyarı verilir.
        inner_center = outer_info["center"]
        inner_diameter = outer_info["diameter"] * 0.55

        inner_info = {
            "center": inner_center,
            "diameter": inner_diameter,
            "ellipse": None
        }

        warning = "İç kontur net bulunamadı, iç çap yaklaşık olarak hesaplandı."

    else:
        # Eğer kullanıcı çok damarlı kablo seçmişse birden fazla iç kontur birlikte değerlendirilir.
        if "çok" in cable_type.lower():
            # Çok damarlı kabloda iç damarlar parçalı konturlar olarak gelebilir.
            # Bu yüzden tüm iç kontur noktalarını birleştirip onları kapsayan minimum çember hesaplıyoruz.
            all_inner_points = np.vstack(candidate_inner_contours)

            (cx_in, cy_in), radius_in = cv2.minEnclosingCircle(all_inner_points)

            inner_info = {
                "center": (float(cx_in), float(cy_in)),
                "diameter": float(radius_in * 2),
                "ellipse": None
            }

            inner_contours_to_draw = candidate_inner_contours

        else:
            # Tek damarlı kabloda en büyük iç kontur iletken/iç bölge sınırı kabul edilir.
            inner_contour = max(candidate_inner_contours, key=cv2.contourArea)

            inner_info = _get_ellipse_info(inner_contour)

            inner_contours_to_draw = [inner_contour]

    # ------------------------------------------------------------
    # 8. Merkez, çap ve yarıçap bilgilerini çıkarma
    # ------------------------------------------------------------
    outer_center = outer_info["center"]
    inner_center = inner_info["center"]

    outer_diameter_px = float(outer_info["diameter"])
    inner_diameter_px = float(inner_info["diameter"])

    outer_radius = outer_diameter_px / 2.0
    inner_radius = inner_diameter_px / 2.0

    # ------------------------------------------------------------
    # 9. Açısal izolasyon kalınlığı ölçümü
    # ------------------------------------------------------------
    thickness_measurements_px = []
    measurement_lines = []

    # Ölçüm sayısı minimum 1 olmalı.
    # Arayüzde zaten 6 veriyoruz, ama backend tarafında da güvenlik ekliyoruz.
    if measurement_count < 1:
        measurement_count = 6

    for i in range(measurement_count):
        # 2*pi tam çemberdir.
        # measurement_count = 6 ise 60 derecelik aralıklarla ölçüm yapılır.
        angle = 2 * np.pi * i / measurement_count

        outer_point = _point_on_circle(outer_center, outer_radius, angle)
        inner_point = _point_on_circle(inner_center, inner_radius, angle)

        thickness_px = _distance(outer_point, inner_point)

        thickness_measurements_px.append(thickness_px)
        measurement_lines.append((inner_point, outer_point))

    # ------------------------------------------------------------
    # 10. Pikselden milimetreye dönüşüm
    # ------------------------------------------------------------
    thickness_measurements_mm = [
        round(value * pixel_to_mm, 3)
        for value in thickness_measurements_px
    ]

    outer_diameter_mm = outer_diameter_px * pixel_to_mm
    inner_diameter_mm = inner_diameter_px * pixel_to_mm

    # ------------------------------------------------------------
    # 11. Eksen kaçıklığı hesaplama
    # ------------------------------------------------------------
    # Eksen kaçıklığı, dış merkez ile iç merkez arasındaki mesafedir.
    eccentricity_px = _distance(outer_center, inner_center)
    eccentricity_mm = eccentricity_px * pixel_to_mm

    # ------------------------------------------------------------
    # 12. Sonuç görselini oluşturma
    # ------------------------------------------------------------
    result_image = original.copy()

    # Dış kontur mavi çizilir.
    cv2.drawContours(result_image, [outer_contour], -1, (255, 0, 0), 3)

    # İç kontur veya iç konturlar kırmızı çizilir.
    for inner_contour_item in inner_contours_to_draw:
        cv2.drawContours(result_image, [inner_contour_item], -1, (0, 0, 255), 3)

    # Merkez koordinatlarını integer'a çeviriyoruz.
    outer_center_int = (int(outer_center[0]), int(outer_center[1]))
    inner_center_int = (int(inner_center[0]), int(inner_center[1]))

    # O1: dış kablo merkezi
    # O2: iç iletken merkezi
    cv2.circle(result_image, outer_center_int, 6, (255, 255, 0), -1)
    cv2.circle(result_image, inner_center_int, 6, (0, 255, 255), -1)

    cv2.putText(
        result_image,
        "O1 Outer",
        (outer_center_int[0] + 10, outer_center_int[1]+15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 0),
        2
    )

    cv2.putText(
        result_image,
        "O2 Inner",
        (inner_center_int[0] + 10, inner_center_int[1]-10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 255),
        2
    )

    # ------------------------------------------------------------
    # 13. Ölçüm çizgilerini çizme
    # ------------------------------------------------------------
    min_index = int(np.argmin(thickness_measurements_px))

    for index, (inner_point, outer_point) in enumerate(measurement_lines):
        # Normal ölçüm çizgileri yeşil çizilir.
        line_color = (0, 255, 0)
        line_thickness = 2

        # Minimum kalınlık çizgisi turuncu ve daha kalın çizilir.
        if index == min_index:
            line_color = (0, 165, 255)
            line_thickness = 4

        cv2.line(
            result_image,
            inner_point,
            outer_point,
            line_color,
            line_thickness
        )

    # Görsel üzerine minimum kalınlık değeri yazılır.
    cv2.putText(
        result_image,
        f"min={min(thickness_measurements_mm):.3f} mm",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 165, 255),
        2
    )

    # ------------------------------------------------------------
    # 14. Sonuç görselini kaydetme
    # ------------------------------------------------------------
    output_dir = os.path.join("backend", "outputs")
    os.makedirs(output_dir, exist_ok=True)

    output_filename = f"result_{uuid.uuid4().hex}.jpg"
    output_path = os.path.join(output_dir, output_filename)

    cv2.imwrite(output_path, result_image)

    # ------------------------------------------------------------
    # 15. JSON uyumlu sonuç döndürme
    # ------------------------------------------------------------
    return {
        "image_name": image_name,
        "cable_type": cable_type,
        "section_id": section_id,
        "section_date": section_date,
        "pixel_to_mm": pixel_to_mm,
        "measurement_count": measurement_count,

        "outer_center_px": [
            round(outer_center[0], 2),
            round(outer_center[1], 2)
        ],
        "inner_center_px": [
            round(inner_center[0], 2),
            round(inner_center[1], 2)
        ],

        "outer_diameter_px": round(outer_diameter_px, 2),
        "inner_diameter_px": round(inner_diameter_px, 2),

        "outer_diameter_mm": round(outer_diameter_mm, 3),
        "inner_diameter_mm": round(inner_diameter_mm, 3),

        "thickness_measurements_mm": thickness_measurements_mm,

        "min_thickness_mm": round(min(thickness_measurements_mm), 3),
        "max_thickness_mm": round(max(thickness_measurements_mm), 3),
        "mean_thickness_mm": round(float(np.mean(thickness_measurements_mm)), 3),

        "eccentricity_px": round(eccentricity_px, 2),
        "eccentricity_mm": round(eccentricity_mm, 3),

        "output_image_url": f"/outputs/{output_filename}",
        "warning": warning
    }