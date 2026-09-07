from services.live_verification import VerificationFormEngine

class Dummy:
    pass

engine = VerificationFormEngine.__new__(
    VerificationFormEngine
)

# Tolak -> Lembaga: bukti eksplisit
ev = engine._reject_destination_evidence(
    decision="reject_institution",
    response_text="",
    detail_text="",
    queue_record={
        "catatan": "Catatan kanwil ke lembaga : mohon RAB diperbaiki",
        "catatan_kabupaten": "",
        "catatan_wilayah": "mohon RAB diperbaiki",
    },
)

assert ev["confirmed"] is True
assert ev["destination"] == "Lembaga"

# Tolak -> Kabupaten: tanpa bukti eksplisit harus BELUM terkonfirmasi.
ev2 = engine._reject_destination_evidence(
    decision="reject_district",
    response_text="",
    detail_text="",
    queue_record={
        "catatan": "mohon diperbaiki",
        "catatan_kabupaten": "",
        "catatan_wilayah": "mohon diperbaiki",
    },
)

assert ev2["confirmed"] is False
assert ev2["destination"] == "Kabupaten"

# Tolak -> Kabupaten: bila SIMBA memberikan bukti eksplisit.
ev3 = engine._reject_destination_evidence(
    decision="reject_district",
    response_text="Catatan kanwil ke kabupaten : mohon diverifikasi ulang",
    detail_text="",
    queue_record={},
)

assert ev3["confirmed"] is True
assert ev3["destination"] == "Kabupaten"

# Catatan perbaikan terbaca kembali.
note = engine._note_saved_evidence(
    expected_note="Mohon RAB diperbaiki",
    queue_record={
        "catatan": "Catatan kanwil ke lembaga : Mohon RAB diperbaiki",
        "catatan_kabupaten": "",
        "catatan_wilayah": "",
    },
    response_text="",
    detail_text="",
)

assert note["confirmed"] is True

print("POST VERIFICATION V7 OK")
