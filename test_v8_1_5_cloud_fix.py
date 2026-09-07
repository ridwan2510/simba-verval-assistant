from services.simba_client import SimbaClient

raw = (
    "https://simba.kemenag.go.id/wilayah/verifikasi/130/"
    "diverifikasikabupaten/data-index/33/all?"
    "draw=1&columns%5B0%5D%5Bdata%5D=DT_Row_Index&"
    "search%5Bvalue%5D=AL%20ITTIHAD&"
    "search%5Bregex%5D=false&start=0&length=25&_="
    "1788753521764&custom=keepme"
)

clean, removed = SimbaClient.sanitize_datatable_url(raw)

assert "draw=" not in clean
assert "columns%5B" not in clean
assert "search%5B" not in clean
assert "start=" not in clean
assert "length=" not in clean
assert "_=" not in clean
assert "custom=keepme" in clean
assert removed

print("V8.1.5 STREAMLIT CLOUD FIX OK")
