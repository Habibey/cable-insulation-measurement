from pydantic import BaseModel
from typing import List, Optional


class CableMeasurementResult(BaseModel):
    image_name: str
    cable_type: str
    section_id: str
    section_date: str
    pixel_to_mm: float
    measurement_count: int

    outer_center_px: List[float]
    inner_center_px: List[float]

    outer_diameter_px: float
    inner_diameter_px: float

    outer_diameter_mm: float
    inner_diameter_mm: float

    thickness_measurements_mm: List[float]

    min_thickness_mm: float
    max_thickness_mm: float
    mean_thickness_mm: float

    eccentricity_px: float
    eccentricity_mm: float

    output_image_url: str
    warning: Optional[str] = None