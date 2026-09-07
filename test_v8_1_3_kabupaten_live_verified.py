from services.live_verification import VerificationFormEngine

class DummyClient:
    base_url = "https://simba.kemenag.go.id"

engine = VerificationFormEngine.__new__(VerificationFormEngine)
engine.client = DummyClient()
engine.submission_log = None

html = r'''\
<html><head><meta name="csrf-token" content="abc"></head><body>
<form method="POST" enctype="multipart/form-data"
 action="/wilayah/simpan-rekomendasi-wilayah/130/diverifikasikabupaten/33/all/356593">
  <input type="hidden" name="_token" value="REDACTED">
  <input id="terima" type="radio" name="terima_tolak" value="terima">
  <label for="terima">Verifikasi Proposal</label>
  <input id="tolak" type="radio" name="terima_tolak" value="tolak">
  <label for="tolak">Tolak Proposal (Revisi), dan Kembalikan ke Lembaga</label>
  <input type="file" name="path_rekomendasi_wilayah">
  <textarea name="catatan_wilayah"></textarea>
  <input type="file" name="files">
</form>
</body></html>
'''

parsed = engine._parse_page(
    html,
    page_url=(
        "https://simba.kemenag.go.id/wilayah/verifikasi/130/"
        "diverifikasikabupaten/33/all/356593/show/rekomendasi_wilayah"
    ),
)
assert "reject_district" not in parsed["decision_forms"]

parsed = engine._inject_verified_district_choice(parsed)
assert parsed["district_verified_network_fallback"] is True
assert "reject_district" in parsed["decision_forms"]

form = parsed["decision_forms"]["reject_district"]
choice = form["decision_map"]["reject_district"]
assert choice["field"] == "terima_tolak"
assert choice["value"] == "tolak_kabupaten"
assert choice["source"] == "verified_network_capture"
assert form["note_field"] == "catatan_wilayah"
assert form["file_field_names"] == ["path_rekomendasi_wilayah", "files"]

safety = engine._validate_reject_routes(parsed)
assert safety["safe"] is True
assert safety["institution_fingerprint"] != safety["district_fingerprint"]

public = engine._public_form(form, decision="reject_district")
assert public["ready"] is True
assert public["decision_source"] == "verified_network_capture"
assert public["decision_value"] == "tolak_kabupaten"
assert public["file_field_names"] == ["path_rekomendasi_wilayah", "files"]

payload = engine._payload_for_decision(
    form,
    decision="reject_district",
    note="Mohon diperbaiki",
)
assert ("terima_tolak", "tolak_kabupaten") in payload
assert ("catatan_wilayah", "Mohon diperbaiki") in payload
assert any(name == "_token" for name, _ in payload)

# Schema mismatch must not activate fallback.
bad_html = html.replace('value="tolak"', 'value="reject"')
bad = engine._parse_page(
    bad_html,
    page_url="https://simba.kemenag.go.id/x",
)
bad = engine._inject_verified_district_choice(bad)
assert "reject_district" not in bad["decision_forms"]

print("V8.1.3 KABUPATEN LIVE VERIFIED OK")
