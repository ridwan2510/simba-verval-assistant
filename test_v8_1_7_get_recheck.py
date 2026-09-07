from pathlib import Path
from services.live_verification import VerificationFormEngine

app = Path("app.py").read_text(encoding="utf-8")
live = Path("services/live_verification.py").read_text(encoding="utf-8")

assert "Periksa Ulang Hasil SIMBA (GET saja)" in app
assert "tidak mengirim keputusan" in app
assert "processed_lookup_attempts" in live
assert '"application_id", target_id' in live
assert '"nspp", institution.nspp' in live
assert '"nama_lembaga", institution.name' in live
assert '"unfiltered_scan"' in live

params = {
    "draw": "4",
    "start": "0",
    "length": "2",
    "search[value]": "LEMBAGA LAMA",
    "columns[0][data]": "id",
    "order[0][column]": "0",
    "custom_filter": "keep",
}

cleaned = VerificationFormEngine._clean_lookup_extra_params(params)
assert cleaned == {"custom_filter": "keep"}

start = app.index("Periksa Ulang Hasil SIMBA (GET saja)")
end = app.find("st.rerun()", start)
block = app[start:end]
assert "verify_after_submit" in block
assert "submit_once(" not in block

print("V8.1.7 GET RECHECK OK")
