from pathlib import Path
from services.simba_client import SimbaClient

app = Path("app.py").read_text(encoding="utf-8")
client = Path("services/simba_client.py").read_text(encoding="utf-8")

assert "PROPOSAL_CONTEXT_CACHE_TTL = 600" in app
assert "LIVE_INSPECTION_CACHE_TTL = 60" in app
assert '"proposal_context_cache": {}' in app
assert '"verification_inspection_cache": {}' in app
assert "Refresh Proposal" in app
assert "review_html_text" in client
assert "parse_profile_html" in client
assert "get_proposal_completeness_html" in client
assert "discover_review_ajax_urls_html" in client
assert "page_size=100" in app

# Parser HTML tidak membutuhkan koneksi SIMBA.
dummy = object.__new__(SimbaClient)

profile_html = """
<html><body><table>
<tr><td>Nama Lembaga:</td><td>Pesantren Contoh</td></tr>
<tr><td>NSPP:</td><td>123456789</td></tr>
</table></body></html>
"""
profile = SimbaClient.parse_profile_html(dummy, profile_html)
assert profile["Nama Lembaga"] == "Pesantren Contoh"
assert profile["NSPP"] == "123456789"

review_html = """
<html><body>
<div>Kelengkapan Persyaratan: 7 dari 9</div>
<script>
var t = $('#x').DataTable({
  ajax: '/wilayah/review/file-proposal/data-index/123'
});
</script>
</body></html>
"""
complete = SimbaClient.get_proposal_completeness_html(dummy, review_html)
assert complete["completed"] == 7
assert complete["total"] == 9

# make_url butuh base_url.
dummy.base_url = "https://simba.kemenag.go.id"
urls = SimbaClient.discover_review_ajax_urls_html(
    dummy,
    "https://simba.kemenag.go.id/wilayah/review/123",
    review_html,
)
assert any("file-proposal" in u for u in urls)

print("V8.1.6 LAN PERFORMANCE OK")
