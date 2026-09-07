from services.live_verification import VerificationFormEngine

class DummyClient:
    base_url = "https://simba.kemenag.go.id"

    def make_url(self, value):
        if value.startswith("http"):
            return value
        return self.base_url + value

engine = VerificationFormEngine.__new__(
    VerificationFormEngine
)
engine.client = DummyClient()
engine.submission_log = None

# Tolak Lembaga boleh dikenali walau Kabupaten tidak ada.
html = """
<form method="POST" action="/wilayah/simpan-rekomendasi-wilayah/130/diverifikasikabupaten/33/all/360087">
  <label for="a">Verifikasi Proposal</label>
  <input id="a" type="radio" name="terima_tolak" value="terima">

  <label for="b">Tolak Proposal (Revisi), dan Kembalikan ke Lembaga</label>
  <input id="b" type="radio" name="terima_tolak" value="tolak">

  <textarea name="catatan_wilayah"></textarea>
</form>
"""

parsed = engine._parse_page(
    html,
    page_url="https://simba.kemenag.go.id/wilayah/verifikasi/130/diverifikasikabupaten/33/all/360087/show/rekomendasi_wilayah",
)

assert "approve" in parsed["decision_forms"]
assert "reject_institution" in parsed["decision_forms"]
assert "reject_district" not in parsed["decision_forms"]

# Endpoint hasil Kanwil harus bisa dibentuk dari detail URL.
processed = engine._derive_processed_ajax_url(
    institution_ajax_url="",
    detail_url=(
        "https://simba.kemenag.go.id/wilayah/verifikasi/"
        "130/diverifikasikabupaten/33/all/360087/show/pesantren"
    ),
)

assert processed == (
    "https://simba.kemenag.go.id/wilayah/verifikasi/"
    "130/diproseskanwil/data-index/33/all"
)

print("V7.2 SAFE LIVE OK")
