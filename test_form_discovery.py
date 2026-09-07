from services.live_verification import VerificationFormEngine

class DummyClient:
    base_url = "https://simba.example"

engine = VerificationFormEngine.__new__(VerificationFormEngine)
engine.client = DummyClient()
engine.submission_log = None

html = """
<html>
<head><meta name="csrf-token" content="SECRET"></head>
<body>
<form method="POST" action="/wilayah/verifikasi/save">
<input type="hidden" name="_token" value="SECRET">
<input type="hidden" name="proposal_id" value="123">

<label for="ok">Verifikasi Proposal</label>
<input id="ok" type="radio" name="hasil_verifikasi" value="1">

<label for="lembaga">Tolak Proposal (Revisi), dan Kembalikan ke Lembaga</label>
<input id="lembaga" type="radio" name="hasil_verifikasi" value="2">

<label for="kab">Tolak Proposal (Revisi), dan Kembalikan ke Kabupaten</label>
<input id="kab" type="radio" name="hasil_verifikasi" value="3">

<label for="catatan">Catatan Perbaikan</label>
<textarea id="catatan" name="catatan_wilayah"></textarea>

<button type="submit">Simpan</button>
</form>
</body>
</html>
"""

parsed = engine._parse_page(
    html,
    page_url="https://simba.example/wilayah/verifikasi/123",
)

assert set(parsed["decision_forms"]) == {
    "approve",
    "reject_institution",
    "reject_district",
}

form = parsed["decision_forms"]["approve"]
assert form["method"] == "POST"
assert form["decision_map"]["approve"]["field"] == "hasil_verifikasi"
assert form["decision_map"]["approve"]["value"] == "1"
assert form["decision_map"]["reject_institution"]["value"] == "2"
assert form["decision_map"]["reject_district"]["value"] == "3"
assert form["note_field"] == "catatan_wilayah"

payload = engine._payload_for_decision(
    form,
    decision="reject_institution",
    note="Mohon RAB diperbaiki",
)

assert ("hasil_verifikasi", "2") in payload
assert ("catatan_wilayah", "Mohon RAB diperbaiki") in payload
assert ("_token", "SECRET") in payload

print("FORM DISCOVERY OK")
