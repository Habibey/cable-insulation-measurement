document.getElementById("sectionDate").valueAsDate = new Date();

async function measureCable() {
  const imageInput = document.getElementById("imageInput");
  const status = document.getElementById("status");

  if (!imageInput.files.length) {
    alert("Lütfen bir kesit görüntüsü seçin.");
    return;
  }

  status.innerText = "Hesaplama yapılıyor...";

  const formData = new FormData();
  formData.append("image", imageInput.files[0]);
  formData.append("cable_type", document.getElementById("cableType").value);
  formData.append("section_id", document.getElementById("sectionId").value);
  formData.append("section_date", document.getElementById("sectionDate").value);
  formData.append("pixel_to_mm", document.getElementById("pixelToMm").value);
  formData.append("measurement_count", document.getElementById("measurementCount").value);

  try {
    const response = await fetch("/api/measure", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error("API hatası oluştu.");
    }

    showResults(data);
    status.innerText = "Hesaplama tamamlandı.";
  } catch (error) {
    console.error(error);
    status.innerText = "Hata oluştu. Terminal çıktısını kontrol edin.";
  }
}

function showResults(data) {
  document.getElementById("outerCenter").innerText = data.outer_center_px.join(", ");
  document.getElementById("innerCenter").innerText = data.inner_center_px.join(", ");

  document.getElementById("outerDiameter").innerText =
    `${data.outer_diameter_px} px / ${data.outer_diameter_mm} mm`;

  document.getElementById("innerDiameter").innerText =
    `${data.inner_diameter_px} px / ${data.inner_diameter_mm} mm`;

  document.getElementById("minThickness").innerText = `${data.min_thickness_mm} mm`;
  document.getElementById("maxThickness").innerText = `${data.max_thickness_mm} mm`;
  document.getElementById("meanThickness").innerText = `${data.mean_thickness_mm} mm`;

  document.getElementById("eccentricity").innerText =
    `${data.eccentricity_px} px / ${data.eccentricity_mm} mm`;

  document.getElementById("measurements").innerText =
    data.thickness_measurements_mm.join(" mm, ") + " mm";

  document.getElementById("warning").innerText = data.warning || "-";

  const resultImage = document.getElementById("resultImage");
  resultImage.src = data.output_image_url + "?t=" + new Date().getTime();

  document.getElementById("jsonOutput").innerText =
    JSON.stringify(data, null, 2);
}