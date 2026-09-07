from services.live_verification import VerificationFormEngine
from services.checklist_service import (
    get_document_reminders,
    get_rules_for_document,
)

engine = VerificationFormEngine.__new__(
    VerificationFormEngine
)
engine.submission_log = None

assert engine._status_matches_decision(
    "Ditolak kanwil ke kabupaten",
    "reject_district",
)

destination = engine._reject_destination_evidence(
    decision="reject_district",
    response_text="",
    detail_text="",
    queue_record={
        "status": "Ditolak kanwil ke kabupaten",
        "catatan": "Catatan kanwil ke kabupaten : Mohon diperbaiki",
        "catatan_kabupaten": "Catatan kanwil ke kabupaten : Mohon diperbaiki",
        "catatan_wilayah": "Mohon diperbaiki",
    },
)

assert destination["confirmed"] is True
assert destination["destination"] == "Kabupaten"
assert destination["source"] in {
    "queue.status",
    "queue.catatan",
    "queue.catatan_kabupaten",
}

title, rules = get_rules_for_document(
    "Surat Rekomendasi Kabupaten",
    aid_title=(
        "Bantuan Halaqah Pesantren dan "
        "Pendidikan Keagamaan Islam"
    ),
    aid_id="130",
)

assert title == "Surat Rekomendasi"
assert any(
    "direktur jenderal pendidikan islam" in rule.lower()
    and "direktur pesantren" in rule.lower()
    for rule in rules
)

reminder_text = " ".join(
    get_document_reminders(
        "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam",
        "130",
        "Surat Rekomendasi Kabupaten",
    )
).lower()

assert "pengingat operasional verval" in reminder_text
assert "direktur jenderal pendidikan islam" in reminder_text
assert "direktur pesantren" in reminder_text

print("V8.1.2 KABUPATEN RESULT VERIFIED OK")
