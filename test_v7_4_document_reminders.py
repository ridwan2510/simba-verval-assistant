from services.checklist_service import (
    get_document_reminders,
)


def joined(aid, doc, aid_id=""):
    return " ".join(
        get_document_reminders(
            aid_title=aid,
            aid_id=aid_id,
            document_name=doc,
        )
    ).lower()


halaqah_rab = joined(
    "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam Tahun Anggaran 2026",
    "Rencana Anggaran Biaya (RAB)",
    "130",
)
assert "rp50.000.000" in halaqah_rab
assert "volume" in halaqah_rab
assert "grand total" in halaqah_rab

kemitraan_rab = joined(
    "Kemitraan Pesantren dan Pendidikan Keagamaan Islam",
    "RAB",
)
assert "rp100.000.000" in kemitraan_rab

prasarana_rab = joined(
    "Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam",
    "Rencana Anggaran Biaya",
)
assert "rp100.000.000" in prasarana_rab
assert "kriteria khusus" in prasarana_rab

prasarana_izin = joined(
    "Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam",
    "Piagam Statistik/Izin Operasional/Izin Pendirian Lembaga",
)
assert "5 tahun" in prasarana_izin
assert "pembaruan" in prasarana_izin
assert "kriteria khusus" in prasarana_izin

sk = joined(
    "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam",
    "Surat Keputusan Kepengurusan yang sah dan masih berlaku",
    "130",
)
assert "ormas" in sk
assert "konsideran" in sk
assert "diktum" in sk

akta = joined(
    "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam",
    "Akta Notaris",
    "130",
)
assert "bukan otomatis" in akta
assert "lpq" in akta

badan_hukum = joined(
    "Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam",
    "Surat Badan Hukum dari Kemenkumham",
    "130",
)
assert "ormas" in badan_hukum
assert "syarat universal" in badan_hukum

fallback = joined(
    "Program Bantuan Lain",
    "Dokumen Tambahan XYZ",
)
assert fallback.strip()
assert "identitas lembaga" in fallback

print("V7.4 DOCUMENT REMINDERS OK")
