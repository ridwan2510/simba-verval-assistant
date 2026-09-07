from services.live_verification import (
    VerificationFormEngine,
    _decision_from_text,
)

assert _decision_from_text("Kembalikan ke Lembaga") == "reject_institution"
assert _decision_from_text("Tolak Proposal (Revisi), dan Kembalikan ke Lembaga") == "reject_institution"
assert _decision_from_text("Kembalikan ke Kabupaten") == "reject_district"
assert _decision_from_text("Kembalikan ke Kabupaten/Kota") == "reject_district"
assert _decision_from_text("Tolak ke Kabupaten") == "reject_district"
assert _decision_from_text("Verifikasi Proposal") == "approve"

class DummyClient:
    base_url = "https://simba.example"

engine = VerificationFormEngine.__new__(
    VerificationFormEngine
)
engine.client = DummyClient()
engine.submission_log = None

html = """
<form method="POST" action="/save">
  <div class="radio-row">
    <input type="radio" name="hasil" value="1">
    <span>Verifikasi Proposal</span>
  </div>
  <div class="radio-row">
    <input type="radio" name="hasil" value="2">
    <span>Kembalikan ke Lembaga</span>
  </div>
  <div class="radio-row">
    <input type="radio" name="hasil" value="3">
    <span>Kembalikan ke Kabupaten</span>
  </div>
  <textarea name="catatan"></textarea>
</form>
"""

parsed = engine._parse_page(
    html,
    page_url="https://simba.example/verifikasi",
)

assert set(
    parsed["decision_forms"]
) == {
    "approve",
    "reject_institution",
    "reject_district",
}

safety = engine._validate_reject_routes(
    parsed
)
assert safety["safe"] is True

print("REJECT LABEL VARIANTS V7.1 OK")
