from pathlib import Path

app = Path("app.py").read_text(encoding="utf-8")

assert "Tutorial Penggunaan Aplikasi" in app
assert "Login ke SIMBA" in app
assert "Fetch/XHR" in app
assert "General → Request URL" in app
assert "Cookie Session" in app
assert "render_usage_tutorial" in app

assets = Path("assets/tutorial")
expected = [
    "01_pengajuan.png",
    "02_inspect.png",
    "03_network.png",
    "04_fetch_xhr.png",
    "05_request_url.png",
    "06_cookie_redacted.png",
]
for name in expected:
    assert (assets / name).exists(), name

# Never bundle the user's original unredacted cookie screenshot.
assert not (assets / "6ac9ad27-284c-4831-8189-1ad1e7b642fb.png").exists()

print("V8.1.4 TUTORIAL OK")
