from pathlib import Path

src = Path("app.py").read_text(encoding="utf-8")

radio_pos = src.index("decision_label = st.radio")
init_pos = src.index("form_inspection = {}", radio_pos)
ready_msg_pos = src.index("LIVE Tolak → Kabupaten aktif", init_pos)
assert radio_pos < init_pos < ready_msg_pos

pre_init = src[radio_pos:init_pos]
assert "district_form_info = form_inspection" not in pre_init
assert 'form_inspection.get("decisions"' not in pre_init

print("V8.1.1 NAMEERROR FIX OK")
