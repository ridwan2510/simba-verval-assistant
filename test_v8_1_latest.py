from services.checklist_service import get_document_reminders, get_rules_for_document
from services.live_verification import VerificationFormEngine

title, rules = get_rules_for_document("Surat Permohonan Bantuan", aid_title="Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam", aid_id="130")
assert title == "Surat Permohonan Bantuan"
joined = " ".join(rules).lower()
assert "direktur jenderal pendidikan islam" in joined and "c.q. direktur pesantren" in joined

pras = " ".join(get_document_reminders("Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam", "", "Surat Permohonan Bantuan")).lower()
assert "direktur jenderal pendidikan islam" in pras and "direktur pesantren" in pras

kem = " ".join(get_document_reminders("Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam", "", "Surat Permohonan Bantuan")).lower()
assert "kementerian agama c.q. direktorat pendidikan islam" in kem

title, rr = get_rules_for_document("Surat Rekomendasi Kabupaten", aid_title="Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam", aid_id="130")
assert title == "Surat Rekomendasi"
rj = " ".join(rr).lower()
assert all(x in rj for x in ("keberadaan", "keaktifan", "kelayakan"))

class DummyClient:
    base_url = "https://simba.kemenag.go.id"
engine = VerificationFormEngine.__new__(VerificationFormEngine)
engine.client = DummyClient()
html = "<a href='/wilayah/verifikasi/130/route-kabupaten/33/all/1'>Kabupaten</a><a href='https://evil.example/tolak-kabupaten'>x</a><script>var u='/wilayah/rekomendasi/kabupaten/1';</script>"
urls = engine._related_decision_urls(html, page_url="https://simba.kemenag.go.id/wilayah/verifikasi/130/current/33/all/1")
assert urls and all(u.startswith("https://simba.kemenag.go.id/") for u in urls) and not any("evil.example" in u for u in urls)
print("V8.1 LATEST OK")
