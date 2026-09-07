from pathlib import Path
from services.checklist_service import (
    detect_program_key,
    get_document_reminders,
    get_rules_for_document,
)

# Program detection
assert detect_program_key(
    "Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam Tahun Anggaran 2026"
) == "kemitraan"
assert detect_program_key(
    "Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam"
) == "prasarana"
assert detect_program_key(
    "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam"
) == "halaqah"

# Kemitraan nominal + Rencana Program Kerja
reminders = get_document_reminders(
    "Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam",
    "",
    "Rencana Anggaran Biaya (RAB)",
)
joined = " ".join(reminders)
assert "Rp100.000.000" in joined

title, rules = get_rules_for_document(
    "Rencana Program Kerja",
    aid_title="Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam",
)
assert title == "Rencana Program Kerja Kemitraan"
rules_text = " ".join(rules).lower()
for needle in ("tujuan", "sasaran", "rangkaian", "output", "outcome"):
    assert needle in rules_text

# Kemitraan rekening dan NPWP adalah dokumen pengajuan.
kem_rekening = " ".join(
    get_document_reminders(
        "Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam",
        "",
        "Buku Rekening atas nama Lembaga",
    )
).lower()
assert "bagian dari dokumen pengajuan proposal" in kem_rekening

kem_npwp = " ".join(
    get_document_reminders(
        "Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam",
        "",
        "NPWP atas nama Lembaga",
    )
).lower()
assert "bagian dari dokumen pengajuan proposal" in kem_npwp

# Kemitraan tidak memaksakan SKT sebagai lampiran utama.
kem_skt = " ".join(
    get_document_reminders(
        "Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam",
        "",
        "Surat Keterangan Terdaftar (SKT)",
    )
).lower()
assert "tidak mencantumkan skt" in kem_skt

# Halaqah rekening/NPWP tetap dibedakan dari proposal awal.
halaqah_rekening = " ".join(
    get_document_reminders(
        "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam",
        "130",
        "Buku Rekening atas nama Lembaga",
    )
).lower()
assert "administrasi pencairan" in halaqah_rekening

# Prasarana: reminder izin 5 tahun harus kondisional.
pras_izin = " ".join(
    get_document_reminders(
        "Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam",
        "",
        "Izin Operasional/Izin Pendirian Lembaga",
    )
).lower()
assert "jika dokumen izin menyatakan masa berlaku 5 tahun" in pras_izin
assert "sah dan masih berlaku" in pras_izin

# Prasarana: dokumen lahan.
pras_lahan = " ".join(
    get_document_reminders(
        "Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam",
        "",
        "Dokumen Kepemilikan Lahan",
    )
).lower()
assert "tidak dalam status sengketa" in pras_lahan

# Deploy files
required = [
    "README.md",
    "DEPLOY_STREAMLIT.md",
    "SECURITY.md",
    "runtime.txt",
    ".streamlit/config.toml",
    ".streamlit/secrets.toml.example",
]
for item in required:
    assert Path(item).exists(), item

assert not Path(".streamlit/secrets.toml").exists()

gitignore = Path(".gitignore").read_text(encoding="utf-8")
assert ".streamlit/secrets.toml" in gitignore
assert "data/*.json" in gitignore

print("V8 RELEASE READY OK")
