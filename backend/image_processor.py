import cv2
import numpy as np
import os
import uuid
from typing import Dict, Any


def _distance(p1, p2):
    return float(np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2))


def _get_ellipse_info(contour):
    """
    Konturdan merkez ve çap tahmini çıkarır.
    fitEllipse için en az 5 nokta gerekir.
    """
    if len(contour) >= 5:
        ellipse = cv2.fitEllipse(contour)
        (cx, cy), (axis1, axis2), angle = ellipse
        diameter = float((axis1 + axis2) / 2.0)
        return {
            "center": (float(cx), float(cy)),
            "diameter": diameter,
            "ellipse": ellipse
        }

    x, y, w, h = cv2.boundingRect(contour)
    return {
        "center": (float(x + w / 2), float(y + h / 2)),
        "diameter": float((w + h) / 2),
        "ellipse": None
    }


def _point_on_circle(center, radius, angle_rad):
    x = center[0] + radius * np.cos(angle_rad)
    y = center[1] + radius * np.sin(angle_rad)
    return (int(round(x)), int(round(y)))


def process_cable_image(
    image_path: str,
    image_name: str,
    cable_type: str,
    section_id: str,
    section_date: str,
    pixel_to_mm: float,
    measurement_count: int = 6
) -> Dict[str, Any]:

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError("Görüntü okunamadı.")

    original = image.copy()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (7, 7), 0)

    # Otsu threshold: görüntüye göre eşik değerini otomatik seçer.
    _, thresh = cv2.threshold(
        blur,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    # Küçük gürültüleri temizle.
    kernel = np.ones((5, 5), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if len(contours) == 0:
        raise ValueError("Dış kontur bulunamadı.")

    # Dış sınır: en büyük kontur
    outer_contour = max(contours, key=cv2.contourArea)
    outer_info = _get_ellipse_info(outer_contour)

    # İç bölge için ters threshold üzerinden beyaz iç boşluğu/iletken alanını arıyoruz.
    inner_thresh = cv2.bitwise_not(thresh)

    inner_contours, _ = cv2.findContours(
        inner_thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    image_area = image.shape[0] * image.shape[1]

    candidate_inner_contours = []
    outer_area = cv2.contourArea(outer_contour)

    for c in inner_contours:
        area = cv2.contourArea(c)
        if area < 100:
            continue
        if area > image_area * 0.90:
            continue
        if area >= outer_area:
            continue

        M = cv2.moments(c)
        if M["m00"] == 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # İç kontur dış konturun içinde olmalı.
        inside = cv2.pointPolygonTest(outer_contour, (cx, cy), False)
        if inside >= 0:
            candidate_inner_contours.append(c)

    warning = None

    if len(candidate_inner_contours) == 0:
        # Eğer iç kontur bulunamazsa yaklaşık varsayım yapıyoruz.
        inner_center = outer_info["center"]
        inner_diameter = outer_info["diameter"] * 0.55
        inner_info = {
            "center": inner_center,
            "diameter": inner_diameter,
            "ellipse": None
        }
        warning = "İç kontur net bulunamadı, iç çap yaklaşık olarak hesaplandı."
    else:
        inner_contour = max(candidate_inner_contours, key=cv2.contourArea)
        inner_info = _get_ellipse_info(inner_contour)

    outer_center = outer_info["center"]
    inner_center = inner_info["center"]

    outer_diameter_px = float(outer_info["diameter"])
    inner_diameter_px = float(inner_info["diameter"])

    outer_radius = outer_diameter_px / 2.0
    inner_radius = inner_diameter_px / 2.0

    # Basit açısal ölçüm:
    # Her açı için dış yarıçap ile iç yarıçap farkını alıyoruz.
    # Merkez kaçıklığını görselleştirmek için çizgiyi iç merkezden dış yöne çiziyoruz.
    thickness_measurements_px = []
    measurement_lines = []

    for i in range(measurement_count):
        angle = 2 * np.pi * i / measurement_count

        outer_point = _point_on_circle(outer_center, outer_radius, angle)
        inner_point = _point_on_circle(inner_center, inner_radius, angle)

        thickness_px = _distance(outer_point, inner_point)
        thickness_measurements_px.append(thickness_px)
        measurement_lines.append((inner_point, outer_point))

    thickness_measurements_mm = [
        round(v * pixel_to_mm, 3) for v in thickness_measurements_px
    ]

    outer_diameter_mm = outer_diameter_px * pixel_to_mm
    inner_diameter_mm = inner_diameter_px * pixel_to_mm

    eccentricity_px = _distance(outer_center, inner_center)
    eccentricity_mm = eccentricity_px * pixel_to_mm

    # Sonuç görseli
    result_image = original.copy()

    # Dış kontur
    cv2.drawContours(result_image, [outer_contour], -1, (255, 0, 0), 3)

    # İç kontur varsa çiz
    if len(candidate_inner_contours) > 0:
        cv2.drawContours(result_image, [inner_contour], -1, (0, 0, 255), 3)

    # Merkezler
    oc = (int(outer_center[0]), int(outer_center[1]))
    ic = (int(inner_center[0]), int(inner_center[1]))

    cv2.circle(result_image, oc, 6, (255, 255, 0), -1)
    cv2.circle(result_image, ic, 6, (0, 255, 255), -1)

    cv2.putText(result_image, "O1 Outer", (oc[0] + 8, oc[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    cv2.putText(result_image, "O2 Inner", (ic[0] + 8, ic[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

    # Ölçüm çizgileri
    min_index = int(np.argmin(thickness_measurements_px))

    for idx, (p1, p2) in enumerate(measurement_lines):
        color = (0, 255, 0)
        thickness = 2

        if idx == min_index:
            color = (0, 165, 255)
            thickness = 4

        cv2.line(result_image, p1, p2, color, thickness)

    cv2.putText(
        result_image,
        f"min={min(thickness_measurements_mm):.3f} mm",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 165, 255),
        2
    )

    output_dir = os.path.join("backend", "outputs")
    os.makedirs(output_dir, exist_ok=True)

    output_filename = f"result_{uuid.uuid4().hex}.jpg"
    output_path = os.path.join(output_dir, output_filename)

    cv2.imwrite(output_path, result_image)

    return {
        "image_name": image_name,
        "cable_type": cable_type,
        "section_id": section_id,
        "section_date": section_date,
        "pixel_to_mm": pixel_to_mm,
        "measurement_count": measurement_count,

        "outer_center_px": [round(outer_center[0], 2), round(outer_center[1], 2)],
        "inner_center_px": [round(inner_center[0], 2), round(inner_center[1], 2)],

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