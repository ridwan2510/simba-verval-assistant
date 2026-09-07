from services.live_verification import VerificationFormEngine

class DummyClient:
    base_url = "https://simba.example"

engine = VerificationFormEngine.__new__(VerificationFormEngine)
engine.client = DummyClient()
engine.submission_log = None

good_html = """
<form method="POST" action="/save">
<label for="a">Verifikasi Proposal</label>
<input id="a" type="radio" name="hasil" value="1">

<label for="b">Tolak Proposal (Revisi), dan Kembalikan ke Lembaga</label>
<input id="b" type="radio" name="hasil" value="2">

<label for="c">Tolak Proposal (Revisi), dan Kembalikan ke Kabupaten</label>
<input id="c" type="radio" name="hasil" value="3">

<textarea name="catatan"></textarea>
</form>
"""

parsed = engine._parse_page(
    good_html,
    page_url="https://simba.example/verifikasi",
)

safety = engine._validate_reject_routes(parsed)
assert safety["safe"] is True
assert safety["institution_fingerprint"] != safety["district_fingerprint"]

bad_html = """
<form method="POST" action="/save">
<label for="b">Tolak Proposal (Revisi), dan Kembalikan ke Lembaga</label>
<input id="b" type="radio" name="hasil" value="2">

<label for="c">Tolak Proposal (Revisi), dan Kembalikan ke Kabupaten</label>
<input id="c" type="radio" name="hasil" value="2">

<textarea name="catatan"></textarea>
</form>
"""

parsed_bad = engine._parse_page(
    bad_html,
    page_url="https://simba.example/verifikasi",
)

safety_bad = engine._validate_reject_routes(parsed_bad)
assert safety_bad["safe"] is False

print("REJECT ROUTE SAFETY OK")
