# tests/test_project_loading.py
from __future__ import annotations

import os
import pytest
from domain.project import Project

def test_project_file_loading():
    """Gerçek bir proje dosyasının (.cd4) yüklenmesini ve eleman bütünlüğünü test et."""
    # Dosya yollarını alternatifli kontrol et
    candidates = [
        # "cad4/model_projesi.cd4",
        # "model_projesi.cd4",
        # "tests/model_projesi.cd4",
        r"D:\Program\cad4\model_projesi.cd4"
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    
    if path is None:
        pytest.skip("Proje dosyası (.cd4) disk üzerinde bulunamadı, test atlanıyor.")

    # Uygulamanın kullandığı standart yöntemle projeyi yükle (bkz: app_actions.py)
    project = Project.load(path)
    assert project is not None, "Proje yüklenemedi, nesne None döndü."
    
    # Sahne ve matematik model kontrolü
    math_model = project.math_model
    assert math_model is not None, "Projenin matematik modeli (math_model) bulunamadı."

    # Eleman havuzlarının veri yapıları doğrulama
    assert hasattr(math_model, "nodes"), "Nodes havuzu eksik."
    assert hasattr(math_model, "frames"), "Frames havuzu eksik."
    assert hasattr(math_model, "areas"), "Areas havuzu eksik."
    assert hasattr(math_model, "links"), "Links havuzu eksik."

    # Konsola istatistikleri dökelim (gözümüz şenlensin)
    nodes_count = len(math_model.nodes)
    frames_count = len(math_model.frames)
    areas_count = len(math_model.areas)
    links_count = len(math_model.links)
    
    print(f"\n[Proje Analiz Raporu - {os.path.basename(path)}]")
    print(f"  • Node (Düğüm) Sayısı : {nodes_count}")
    print(f"  • Frame (Çubuk) Sayısı: {frames_count}")
    print(f"  • Area (Alan) Sayısı  : {areas_count}")
    print(f"  • Link Sayısı         : {links_count}")

    # ID ve Nesne Tutarlılık Kontrolü
    all_elements = {**math_model.nodes, **math_model.frames, **math_model.areas, **math_model.links}
    for uid, el in all_elements.items():
        assert hasattr(el, "unique_id"), f"Eleman unique_id özelliğine sahip değil: {el}"
        assert el.unique_id == uid, f"ID uyuşmazlığı: Sözlük anahtarı ({uid}) ile eleman ID'si ({el.unique_id}) farklı."
        assert isinstance(el.is_selected, bool), f"Seçim bayrağı (is_selected) boolean değil: {el}"