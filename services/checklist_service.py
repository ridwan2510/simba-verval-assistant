from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


STATUS_NOT_REVIEWED = "Belum diperiksa"
STATUS_OK = "Sesuai"
STATUS_REVISION = "Perlu Perbaikan"
LEGACY_STATUS_INVALID = "Tidak Sesuai"

STATUS_OPTIONS = [STATUS_OK, STATUS_REVISION]


def normalize_name(value: str) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


# Penting: seluruh checklist di bawah adalah TEMUAN NEGATIF.
# Checklist hanya ditampilkan saat status dokumen = Perlu Perbaikan.
GENERIC_RULES = [
    "Dokumen tidak dapat dibuka atau tidak terbaca dengan jelas.",
    "Nama/identitas lembaga tidak konsisten dengan data pengajuan SIMBA.",
    "Dokumen yang diunggah tidak sesuai dengan jenis persyaratan.",
    "Isi dokumen tidak konsisten atau bertentangan dengan dokumen pengajuan lainnya.",
]


RULESETS = [
    {
        "keywords": ["tema kegiatan halaqah", "tema halaqah"],
        "title": "Tema Kegiatan Halaqah",
        "rules": [
            "Tema kegiatan tidak berkaitan secara jelas dengan kegiatan Halaqah.",
            "Tema tidak mendukung tujuan peningkatan kualitas SDM, moderasi beragama, pembangunan karakter, atau mutu pesantren/pendidikan keagamaan Islam.",
            "Tema tidak konsisten dengan rencana kegiatan dan/atau RAB.",
        ],
    },
    {
        "keywords": ["surat permohonan bantuan", "surat permohonan"],
        "title": "Surat Permohonan Bantuan",
        "rules": [
            "Surat tidak menggunakan kop lembaga/organisasi atau alamat lembaga tidak jelas.",
            "Surat tidak ditujukan kepada Direktur Jenderal Pendidikan Islam Kementerian Agama.",
            "Hal surat tidak menyebut pengajuan Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam.",
            "Identitas pimpinan/lembaga pemohon tidak tercantum atau tidak konsisten dengan data SIMBA.",
            "Nomor HP/kontak aktif tidak tercantum.",
            "Surat tidak ditandatangani pimpinan lembaga/organisasi.",
        ],
    },
    {
        "keywords": ["rencana anggaran biaya", "rab"],
        "title": "Rencana Anggaran Biaya (RAB)",
        "rules": [
            "RAB tidak menggunakan identitas/kop lembaga yang sesuai.",
            "RAB tidak memuat uraian, volume, satuan, harga satuan, dan/atau jumlah biaya secara lengkap.",
            "Perhitungan volume × harga satuan, subtotal, dan/atau total biaya tidak konsisten.",
            "Terdapat komponen biaya yang tidak berkaitan langsung dengan penyelenggaraan kegiatan Halaqah.",
            "RAB tidak dapat dipetakan secara wajar pada persiapan, pelaksanaan, dan/atau penyusunan laporan.",
            "Rencana penggunaan bantuan tidak memungkinkan dilaksanakan dalam tahun anggaran berjalan.",
            "Terdapat penggunaan bantuan untuk kegiatan di luar tujuan Juknis atau kegiatan yang bertentangan dengan ketentuan peraturan perundang-undangan.",
            "RAB tidak ditandatangani pimpinan lembaga/organisasi.",
        ],
    },
    {
        "keywords": ["rencana kegiatan", "rencana program kerja", "program kerja"],
        "title": "Rencana Kegiatan Halaqah",
        "rules": [
            "Tujuan kegiatan tidak dicantumkan atau tidak jelas.",
            "Sasaran kegiatan tidak dicantumkan atau tidak jelas.",
            "Rangkaian kegiatan yang akan dilaksanakan tidak dijelaskan dengan memadai.",
            "Hasil langsung (output) yang diharapkan tidak dijelaskan.",
            "Dampak (outcome) yang diharapkan tidak dijelaskan.",
            "Rencana kegiatan tidak konsisten dengan tema kegiatan dan/atau RAB.",
        ],
    },
    {
        "keywords": ["profil singkat pesantren", "profil pesantren", "profil singkat lembaga", "profil lembaga"],
        "title": "Profil Singkat Pesantren",
        "rules": [
            "Profil tidak memuat sejarah singkat dan/atau latar belakang berdiri.",
            "Profil tidak memuat identitas pendiri dan pimpinan/pengasuh.",
            "Profil tidak memuat jumlah santri putra/putri.",
            "Informasi tahassus/kekhususan dalam tafaqquh fiddin tidak dicantumkan apabila memang ada.",
            "Informasi unit usaha tidak dicantumkan apabila memang ada.",
            "Data profil tidak konsisten dengan identitas lembaga pada SIMBA.",
        ],
    },
    {
        "keywords": ["profil singkat lpq", "profil lpq", "profil singkat mdt", "profil mdt"],
        "title": "Profil Singkat LPQ/MDT",
        "rules": [
            "Profil tidak memuat sejarah singkat dan/atau latar belakang berdiri.",
            "Profil tidak memuat identitas pendiri dan pimpinan.",
            "Profil tidak memuat jumlah santri putra/putri.",
            "Informasi tahassus/kekhususan dalam tafaqquh fiddin tidak dicantumkan apabila memang ada.",
            "Informasi unit usaha tidak dicantumkan apabila memang ada.",
            "Data profil tidak konsisten dengan identitas lembaga pada SIMBA.",
        ],
    },
    {
        "keywords": ["profil singkat ormas", "profil ormas", "profil singkat afpspp", "profil afpspp", "profil singkat lsm", "profil lsm"],
        "title": "Profil Singkat Ormas Islam/AFPSPP/LSM",
        "rules": [
            "Profil tidak memuat sejarah berdiri dan/atau latar belakang organisasi.",
            "Profil tidak memuat identitas pendiri dan/atau pimpinan.",
            "Profil tidak memuat jumlah anggota.",
            "Informasi unit usaha tidak dicantumkan apabila memang ada.",
            "Data profil tidak konsisten dengan identitas organisasi pada SIMBA.",
        ],
    },
    {
        "keywords": ["piagam statistik pesantren", "psp"],
        "title": "Piagam Statistik Pesantren (PSP)",
        "rules": [
            "Piagam Statistik Pesantren tidak tersedia atau tidak terbaca dengan jelas.",
            "Nama pesantren pada PSP tidak konsisten dengan pengajuan SIMBA.",
            "Nomor statistik/NSPP pada PSP tidak konsisten dengan data SIMBA.",
            "Dokumen tidak dapat menunjukkan bahwa pesantren terdaftar pada Kementerian Agama.",
        ],
    },
    {
        "keywords": ["surat tanda terdaftar", "skt", "izin pendidikan", "izin operasional"],
        "title": "Izin/SKT LPQ atau MDT",
        "rules": [
            "Dokumen pendaftaran/izin pendidikan tidak tersedia atau tidak terbaca dengan jelas.",
            "Nama LPQ/MDT pada dokumen tidak konsisten dengan data pengajuan.",
            "Nomor dokumen/izin tidak dapat diidentifikasi.",
            "Dokumen sudah tidak berlaku atau masa berlakunya tidak dapat dipastikan dari dokumen.",
        ],
    },
    {
        "keywords": ["surat keputusan kepengurusan", "sk kepengurusan", "keputusan kepengurusan"],
        "title": "Surat Keputusan Kepengurusan",
        "rules": [
            "SK kepengurusan tidak tersedia atau tidak terbaca dengan jelas.",
            "Format dokumen tidak menunjukkan Surat Keputusan (SK) yang utuh atau hanya berupa daftar/susunan pengurus.",
            "SK tidak memuat konsideran/landasan keputusan, seperti bagian Menimbang dan/atau Mengingat.",
            "SK tidak memuat diktum/amar keputusan yang jelas, seperti MEMUTUSKAN/Menetapkan dan butir KESATU, KEDUA, dan seterusnya.",
            "Nama organisasi/lembaga pada SK tidak konsisten dengan pengajuan.",
            "Pimpinan/pengurus yang relevan tidak tercantum atau tidak dapat diidentifikasi.",
            "SK kepengurusan sudah tidak berlaku atau masa berlakunya tidak dapat dipastikan dari dokumen.",
        ],
    },
    {
        "keywords": ["akta notaris"],
        "title": "Akta Notaris",
        "rules": [
            "Akta notaris tidak tersedia atau tidak dapat dibaca dengan jelas.",
            "Nama badan/lembaga tidak konsisten dengan pengajuan SIMBA.",
            "Nomor dan/atau tanggal akta tidak dapat diidentifikasi.",
            "Identitas pendiri/pengurus yang relevan tidak dapat diidentifikasi.",
        ],
    },
    {
        "keywords": ["badan hukum", "kemenkumham", "kementerian hukum"],
        "title": "Badan Hukum Kementerian Hukum",
        "rules": [
            "Dokumen pengesahan/keputusan badan hukum tidak tersedia atau tidak dapat dibaca dengan jelas.",
            "Nama badan hukum tidak konsisten dengan nama pada akta notaris dan/atau pengajuan SIMBA.",
            "Nomor dan/atau tanggal keputusan/pengesahan tidak dapat diidentifikasi.",
            "Dokumen tidak dapat dipastikan berasal dari instansi berwenang di bidang hukum.",
        ],
    },
    {
        "keywords": ["surat rekomendasi kabupaten", "rekomendasi kabupaten", "rekomendasi kankemenag"],
        "title": "Rekomendasi Kantor Kementerian Agama Kabupaten/Kota",
        "rules": [
            "Surat rekomendasi tidak tersedia atau tidak dapat dibaca dengan jelas.",
            "Nama lembaga yang direkomendasikan tidak konsisten dengan pengajuan SIMBA.",
            "Surat tidak berasal dari Kantor Kementerian Agama Kabupaten/Kota yang relevan.",
            "Isi rekomendasi tidak menyatakan keberadaan, keaktifan, dan/atau kelayakan lembaga sebagai penerima bantuan.",
            "Identitas pejabat/penandatangan surat rekomendasi tidak dapat diidentifikasi.",
        ],
    },
    {
        "keywords": ["buku rekening", "rekening atas nama lembaga", "rekening"],
        "title": "Buku Rekening atas Nama Lembaga",
        "rules": [
            "Bukti rekening tidak tersedia atau tidak dapat dibaca dengan jelas.",
            "Nama pemilik rekening bukan atas nama lembaga penerima bantuan atau tidak konsisten dengan identitas lembaga yang sah.",
            "Nama bank dan/atau nomor rekening tidak dapat diidentifikasi.",
            "Data rekening tidak konsisten dengan data rekening pada pengajuan SIMBA.",
        ],
    },
    {
        "keywords": ["npwp", "nomor pokok wajib pajak"],
        "title": "NPWP atas Nama Lembaga",
        "rules": [
            "Dokumen NPWP tidak tersedia atau tidak dapat dibaca dengan jelas.",
            "NPWP bukan atas nama lembaga/organisasi penerima atau identitasnya tidak sesuai.",
            "Nomor NPWP tidak dapat diidentifikasi.",
            "Nama pada NPWP tidak konsisten dengan identitas lembaga pada pengajuan SIMBA.",
        ],
    },
]


def get_rules_for_document(
    document_name: str,
    aid_title: str = "",
    aid_id: str = "",
) -> tuple[str, list[str]]:
    """
    Checklist temuan negatif yang menyesuaikan jenis bantuan.

    aid_title/aid_id opsional supaya fungsi lama dan test lama tetap kompatibel.
    """
    normalized = normalize_name(document_name)
    program = detect_program_key(
        aid_title,
        aid_id,
    )

    # --------------------------------------------------------
    # Surat Permohonan
    # --------------------------------------------------------
    if "surat permohonan" in normalized:
        title = "Surat Permohonan Bantuan"
        rules = [
            "Surat tidak menggunakan kop/identitas lembaga atau alamat lembaga tidak jelas.",
            "Nama lembaga/pimpinan pemohon tidak konsisten dengan data SIMBA.",
            "Nama program bantuan yang diajukan tidak sesuai dengan program pada SIMBA.",
            "Surat tidak ditandatangani pimpinan lembaga/organisasi.",
            "Nomor dan/atau tanggal surat tidak dapat diidentifikasi.",
        ]

        if program == "halaqah":
            rules.extend([
                "Perihal surat tidak menyebut Pengajuan Permohonan Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam.",
                "Surat permohonan tidak ditujukan kepada Direktur Jenderal Pendidikan Islam Kementerian Agama c.q. Direktur Pesantren, di Jakarta, sebagaimana contoh format Juknis Halaqah.",
            ])
        elif program == "prasarana":
            rules.extend([
                "Perihal surat tidak menyebut Pengajuan Permohonan Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam.",
                "Surat permohonan tidak ditujukan kepada Direktur Jenderal Pendidikan Islam Kementerian Agama c.q. Direktur Pesantren, di Jakarta, sebagaimana contoh format Juknis Prasarana.",
            ])
        elif program == "kemitraan":
            rules.extend([
                "Perihal surat tidak sesuai dengan Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam.",
                "Tujuan surat permohonan tidak mengarah kepada Kementerian Agama c.q. Direktorat Pendidikan Islam sebagaimana mekanisme pengajuan yang tertulis pada Juknis Kemitraan.",
            ])

        return title, rules

    # --------------------------------------------------------
    # RAB
    # --------------------------------------------------------
    if (
        "rencana anggaran biaya" in normalized
        or normalized == "rab"
        or " rab " in f" {normalized} "
    ):
        title = "Rencana Anggaran Biaya (RAB)"
        rules = [
            "RAB tidak menggunakan identitas/kop lembaga yang sesuai.",
            "RAB tidak memuat uraian, volume, satuan, harga satuan, dan/atau jumlah biaya secara lengkap.",
            "Perhitungan volume × harga satuan, subtotal, dan/atau grand total tidak konsisten.",
            "Terdapat komponen belanja yang terlalu umum/lump-sum sehingga penggunaan dana tidak dapat diidentifikasi dengan jelas.",
            "Terdapat komponen belanja yang tidak berkaitan dengan tujuan dan pelaksanaan program bantuan.",
            "Rencana penggunaan bantuan tidak memungkinkan dilaksanakan dalam tahun anggaran berjalan.",
            "Terdapat penggunaan bantuan untuk kegiatan yang bertentangan dengan ketentuan peraturan perundang-undangan.",
            "RAB tidak ditandatangani pimpinan lembaga/organisasi.",
        ]

        nominal = PROGRAM_NOMINALS_2026.get(program)
        if nominal:
            rules.insert(
                3,
                "Grand total RAB tidak sesuai dengan nominal program "
                f"{_rupiah(nominal)}."
            )

        if program == "halaqah":
            rules.append(
                "RAB tidak konsisten dengan Rencana Kegiatan Halaqah."
            )
        elif program == "kemitraan":
            rules.append(
                "RAB tidak konsisten dengan Rencana Program Kerja Kemitraan."
            )
        elif program == "prasarana":
            rules.extend(
                [
                    "RAB tidak konsisten dengan jenis pekerjaan pembangunan/rehabilitasi yang diajukan.",
                    "RAB memuat pekerjaan atau volume yang tidak dapat dicocokkan dengan kondisi/foto prasarana yang diajukan.",
                ]
            )

        return title, rules

    # --------------------------------------------------------
    # Rencana Kegiatan / Program Kerja
    # Halaqah dan Kemitraan sama-sama secara eksplisit memuat
    # Tujuan, Sasaran, Rangkaian Kegiatan, output, outcome.
    # --------------------------------------------------------
    if (
        "rencana kegiatan" in normalized
        or "rencana program kerja" in normalized
        or "program kerja" in normalized
    ):
        if program == "halaqah":
            title = "Rencana Kegiatan Halaqah"
        elif program == "kemitraan":
            title = "Rencana Program Kerja Kemitraan"
        else:
            title = "Rencana Kegiatan / Program Kerja"

        rules = [
            "Tujuan kegiatan/program tidak dicantumkan atau tidak jelas.",
            "Sasaran kegiatan/program tidak dicantumkan atau tidak jelas.",
            "Rangkaian kegiatan yang akan dilaksanakan tidak dijelaskan dengan memadai.",
            "Hasil langsung (output) yang ditargetkan tidak dijelaskan.",
            "Dampak (outcome) yang ditargetkan tidak dijelaskan.",
            "Rencana kegiatan/program tidak konsisten dengan RAB dan/atau jenis bantuan.",
        ]
        return title, rules

    # --------------------------------------------------------
    # Profil
    # --------------------------------------------------------
    if "profil" in normalized:
        if "pesantren" in normalized:
            title = "Profil Singkat Pesantren"

            if program == "kemitraan":
                return title, [
                    "Profil tidak memuat sejarah berdiri dan latar belakang berdiri.",
                    "Profil tidak memuat identitas pendiri dan/atau pimpinan.",
                    "Profil tidak memuat jumlah anggota.",
                    "Informasi unit usaha tidak dicantumkan apabila memang ada.",
                    "Data profil tidak konsisten dengan identitas Pesantren pada SIMBA.",
                ]

            if program == "prasarana":
                return title, [
                    "Profil tidak memuat sejarah berdiri dan latar belakang berdiri.",
                    "Profil tidak memuat identitas pendiri dan pengasuh.",
                    "Profil tidak memuat jumlah santri putra dan putri.",
                    "Profil tidak memuat satuan pendidikan Pesantren.",
                    "Informasi takhassus/kekhususan dalam tafaqquh fiddin tidak dicantumkan apabila memang ada.",
                    "Informasi unit usaha tidak dicantumkan apabila memang ada.",
                    "Data profil tidak konsisten dengan identitas Pesantren pada SIMBA.",
                ]

        if "lpq" in normalized or "mdt" in normalized or "satuan pendidikan" in normalized:
            title = "Profil Singkat Satuan Pendidikan Keagamaan Islam"
            return title, [
                "Profil tidak memuat sejarah berdiri dan latar belakang berdiri.",
                "Profil tidak memuat identitas pendiri dan pimpinan.",
                "Profil tidak memuat jumlah santri putra dan putri.",
                "Informasi tahassus/kekhususan dalam tafaqquh fiddin tidak dicantumkan apabila memang ada.",
                "Informasi unit usaha tidak dicantumkan apabila memang ada.",
                "Data profil tidak konsisten dengan identitas lembaga pada SIMBA.",
            ]

        if "ormas" in normalized or "afpspp" in normalized:
            title = "Profil Singkat Ormas Islam/AFPSPP"
            return title, [
                "Profil tidak memuat sejarah berdiri dan latar belakang berdiri.",
                "Profil tidak memuat identitas pendiri dan/atau pimpinan.",
                "Profil tidak memuat jumlah anggota.",
                "Informasi unit usaha tidak dicantumkan apabila memang ada.",
                "Data profil tidak konsisten dengan identitas organisasi pada SIMBA.",
            ]

        if "lsm" in normalized:
            title = "Profil Singkat LSM"
            rules = [
                "Profil tidak memuat sejarah berdiri dan latar belakang berdiri.",
                "Profil tidak memuat identitas pendiri dan/atau pimpinan.",
                "Data profil tidak konsisten dengan identitas LSM pada SIMBA.",
            ]
            if program == "kemitraan":
                rules.extend(
                    [
                        "Profil tidak memuat bidang garapan LSM.",
                        "Informasi unit usaha tidak dicantumkan apabila memang ada.",
                    ]
                )
            else:
                rules.append(
                    "Informasi jumlah anggota dan/atau unit usaha tidak dijelaskan apabila dipersyaratkan/relevan."
                )
            return title, rules

    # --------------------------------------------------------
    # Izin Operasional / Izin Pendirian / Registrasi
    # --------------------------------------------------------
    if (
        "izin operasional" in normalized
        or "izin pendirian" in normalized
        or "izin pendidikan" in normalized
        or "piagam tanda daftar" in normalized
    ):
        return "Izin Operasional / Izin Pendirian / Registrasi", [
            "Dokumen izin/registrasi tidak tersedia atau tidak terbaca dengan jelas.",
            "Nama lembaga pada dokumen tidak konsisten dengan data pengajuan.",
            "Nomor dokumen/izin tidak dapat diidentifikasi.",
            "Tanggal terbit dan/atau masa berlaku dokumen tidak dapat dipastikan.",
            "Dokumen sudah tidak berlaku pada saat pengajuan.",
        ]

    # --------------------------------------------------------
    # Kepemilikan lahan - Prasarana
    # --------------------------------------------------------
    if "kepemilikan lahan" in normalized or "hak atas lahan" in normalized:
        return "Dokumen Kepemilikan/Hak atas Lahan", [
            "Dokumen kepemilikan/hak atas lahan tidak tersedia atau tidak terbaca dengan jelas.",
            "Nama pemilik/pemegang hak tidak dapat dihubungkan dengan lembaga pemohon.",
            "Lokasi/identitas lahan tidak dapat dicocokkan dengan lokasi pekerjaan yang diajukan.",
            "Status hak atas lahan tidak dapat diidentifikasi.",
            "Terdapat indikasi/status sengketa lahan atau dokumen tidak cukup menjelaskan bahwa lahan tidak dalam sengketa.",
        ]

    # --------------------------------------------------------
    # Dokumentasi/foto Prasarana
    # --------------------------------------------------------
    if (
        "foto kondisi lahan" in normalized
        or "dokumentasi kondisi lahan" in normalized
        or "foto lahan" in normalized
    ):
        return "Dokumentasi/Foto Kondisi Lahan", [
            "Foto kondisi lahan tidak tersedia atau tidak dapat dilihat dengan jelas.",
            "Foto tidak menunjukkan lokasi dan ukuran/ruang pekerjaan secara memadai.",
            "Untuk pengajuan pembangunan, dokumentasi tidak menunjukkan kondisi sebelum pekerjaan secara memadai.",
            "Untuk pengajuan pembangunan, dokumentasi tidak memenuhi kebutuhan minimal foto dari beberapa sudut sebagaimana Juknis.",
        ]

    if (
        "foto kondisi bangunan" in normalized
        or "dokumentasi kondisi bangunan" in normalized
        or "foto bangunan" in normalized
    ):
        return "Dokumentasi/Foto Kondisi Bangunan", [
            "Foto kondisi bangunan tidak tersedia atau tidak dapat dilihat dengan jelas.",
            "Foto tidak menunjukkan bagian bangunan yang akan direhabilitasi.",
            "Ukuran/luas bagian yang akan direhabilitasi tidak dapat diidentifikasi dari dokumen pendukung.",
            "Kondisi pada foto tidak konsisten dengan pekerjaan rehabilitasi yang tercantum pada RAB.",
        ]

    # --------------------------------------------------------
    # UPK2 / unit pengelola kegiatan Prasarana
    # --------------------------------------------------------
    if "upk2" in normalized or "unit pengelola kegiatan" in normalized:
        return "SK UPK2 / Unit Pengelola Kegiatan", [
            "SK UPK2/Unit Pengelola Kegiatan tidak tersedia atau tidak terbaca dengan jelas.",
            "SK tidak diterbitkan/ditandatangani pimpinan lembaga yang berwenang.",
            "Susunan UPK2 tidak dapat diidentifikasi.",
            "Jumlah personel UPK2 kurang dari ketentuan minimal yang dipersyaratkan Juknis.",
        ]

    # --------------------------------------------------------
    # Surat Rekomendasi
    # --------------------------------------------------------
    if "rekomendasi" in normalized:
        title = "Surat Rekomendasi"
        rules = [
            "Surat rekomendasi tidak tersedia atau tidak terbaca dengan jelas.",
            "Nama lembaga pada rekomendasi tidak konsisten dengan data SIMBA/proposal.",
            "Nomor dan/atau tanggal surat rekomendasi tidak dapat diidentifikasi.",
            "Pejabat/instansi penerbit rekomendasi tidak dapat diidentifikasi atau tidak sesuai dengan kewenangan yang disebut dalam Juknis.",
            "Surat rekomendasi tidak menyatakan keberadaan lembaga.",
            "Surat rekomendasi tidak menyatakan keaktifan lembaga.",
            "Surat rekomendasi tidak menyatakan kelayakan lembaga sebagai penerima bantuan.",
            "Tujuan/perihal rekomendasi tidak berkaitan dengan program bantuan yang diajukan.",
            "Surat rekomendasi tidak ditujukan kepada Direktur Jenderal Pendidikan Islam c.q. Direktur Pesantren, di Jakarta, sesuai format operasional verval yang digunakan.",
        ]
        if program == "halaqah":
            rules.append("Rekomendasi bukan berasal dari Kanwil Kementerian Agama dan/atau Kantor Kementerian Agama Kabupaten/Kota sebagaimana Juknis Halaqah.")
        elif program == "kemitraan":
            rules.append("Rekomendasi bukan berasal dari Kanwil Kementerian Agama provinsi dan/atau Kantor Kementerian Agama Kabupaten/Kota sebagaimana Juknis Kemitraan.")
        elif program == "prasarana":
            rules.append("Rekomendasi bukan berasal dari Kantor Kementerian Agama Kabupaten/Kota atau mekanisme rekomendasi yang berlaku pada Juknis Prasarana.")
        return title, rules

    # --------------------------------------------------------
    # Base rulesets
    # --------------------------------------------------------
    for ruleset in RULESETS:
        if any(
            normalize_name(keyword) in normalized
            for keyword in ruleset["keywords"]
        ):
            return ruleset["title"], list(ruleset["rules"])

    return document_name or "Dokumen", list(GENERIC_RULES)




PROGRAM_NOMINALS_2026 = {
    "halaqah": 50_000_000,
    "kemitraan": 100_000_000,
    "prasarana": 100_000_000,
}


def detect_program_key(
    aid_title: str,
    aid_id: str = "",
) -> str:
    """
    Kenali program TA 2026.

    ID 130 hanya dipakai sebagai fallback Halaqah karena sudah terverifikasi
    dari alur SIMBA yang digunakan pada pengembangan aplikasi.
    Program lain diutamakan dari judul bantuan yang dibaca dari SIMBA.
    """
    normalized = normalize_name(aid_title)

    if "halaqah" in normalized:
        return "halaqah"

    if "kemitraan" in normalized:
        return "kemitraan"

    if "prasarana" in normalized:
        return "prasarana"

    if str(aid_id or "").strip() == "130":
        return "halaqah"

    return ""


def _rupiah(value: int) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


def get_document_reminders(
    aid_title: str,
    aid_id: str,
    document_name: str,
) -> list[str]:
    """
    Pengingat visual untuk verifikator.

    Pengingat tidak mengambil keputusan otomatis. Verifikator tetap membaca
    dokumen asli, Juknis program, dan data SIMBA.
    """
    name = normalize_name(document_name)
    program = detect_program_key(
        aid_title,
        aid_id,
    )
    nominal = PROGRAM_NOMINALS_2026.get(program)
    reminders: list[str] = []

    # --------------------------------------------------------
    # RAB
    # --------------------------------------------------------
    if (
        "rencana anggaran biaya" in name
        or name == "rab"
        or " rab " in f" {name} "
    ):
        if nominal:
            reminders.append(
                f"Nominal program TA 2026 adalah {_rupiah(nominal)}. "
                "Pastikan seluruh rincian, subtotal, dan grand total konsisten "
                "dengan nominal program."
            )

        reminders.extend(
            [
                "Hitung ulang volume × harga satuan, subtotal, dan grand total; jangan hanya mempercayai angka grand total yang diketik.",
                "Uraian belanja harus konkret, cukup rinci, dan berkaitan dengan tujuan program. Hindari komponen lump-sum/tak terduga yang tidak menjelaskan penggunaan dana.",
            ]
        )

        if program == "halaqah":
            reminders.append(
                "Cocokkan seluruh komponen RAB dengan Rencana Kegiatan Halaqah dan pelaksanaan dalam tahun anggaran berjalan."
            )
        elif program == "kemitraan":
            reminders.append(
                "Cocokkan RAB dengan Rencana Program Kerja Kemitraan. Juknis Kemitraan memfasilitasi kegiatan pendidikan, pelatihan, dan dukungan operasional lembaga mitra sesuai tujuan program."
            )
        elif program == "prasarana":
            reminders.append(
                "Cocokkan RAB dengan jenis pekerjaan pembangunan/rehabilitasi, kondisi lahan/bangunan, ukuran, dan dokumentasi sebelum pekerjaan."
            )

    # --------------------------------------------------------
    # Surat Permohonan
    # --------------------------------------------------------
    elif "surat permohonan" in name:
        if nominal:
            reminders.append(f"Pastikan nama program dan nilai bantuan konsisten dengan SIMBA. Nominal program: {_rupiah(nominal)}.")
        reminders.append("Periksa kop/identitas lembaga, nomor dan tanggal surat, perihal, nama pimpinan, isi permohonan, dan tanda tangan pimpinan.")
        if program == "halaqah":
            reminders.extend([
                "Contoh format Juknis Halaqah menujukan surat kepada: Yth. Direktur Jenderal Pendidikan Islam Kementerian Agama, c.q. Direktur Pesantren, Di Jakarta.",
                "Perihal pada contoh Juknis: Pengajuan Permohonan Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam.",
            ])
        elif program == "prasarana":
            reminders.extend([
                "Contoh format Juknis Prasarana menujukan surat kepada: Yth. Direktur Jenderal Pendidikan Islam Kementerian Agama, c.q. Direktur Pesantren, Di Jakarta.",
                "Perihal pada contoh Juknis: Pengajuan Permohonan Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam.",
            ])
        elif program == "kemitraan":
            reminders.extend([
                "Juknis Kemitraan tidak menampilkan contoh Surat Permohonan pada lampiran yang tersedia. Pada mekanisme pengajuan tertulis bahwa usulan/proposal diajukan kepada Kementerian Agama c.q. Direktorat Pendidikan Islam.",
                "Jangan menjadikan perbedaan tata letak surat sebagai satu-satunya alasan penolakan; utamakan kesesuaian tujuan, program, identitas pemohon, dan tanda tangan pimpinan.",
            ])

    # --------------------------------------------------------
    # PSP / PSLPQ / PSMDT / Izin
    # --------------------------------------------------------
    elif (
        "piagam statistik pesantren" in name
        or " psp " in f" {name} "
        or "pslpq" in name
        or "psmdt" in name
        or "piagam tanda daftar" in name
        or "izin operasional" in name
        or "izin pendirian" in name
        or "izin pendidikan" in name
    ):
        if "piagam statistik pesantren" in name or " psp " in f" {name} ":
            reminders.append(
                "Untuk Pesantren, pastikan Piagam Statistik Pesantren, nama lembaga, nomor statistik/NSPP, dan data SIMBA konsisten."
            )

        if "pslpq" in name:
            reminders.append(
                "Untuk LPQ/TPQ, pastikan registrasi/PSLPQ sesuai dengan identitas lembaga dan data SIMBA."
            )

        if "psmdt" in name:
            reminders.append(
                "Untuk MDT, pastikan registrasi/PSMDT sesuai dengan identitas lembaga dan data SIMBA."
            )

        if (
            "piagam tanda daftar" in name
            or "izin operasional" in name
            or "izin pendirian" in name
            or "izin pendidikan" in name
        ):
            reminders.append(
                "Juknis mensyaratkan izin/registrasi yang sah dan masih berlaku. Periksa tanggal terbit serta masa berlaku yang tertulis pada dokumen."
            )
            reminders.append(
                "Jika dokumen izin menyatakan masa berlaku 5 tahun, hitung 5 tahun dari tanggal terbit/masa berlakunya; apabila sudah berakhir, minta dokumen pembaruan. Jangan menganggap semua izin otomatis 5 tahun bila dokumennya menyatakan lain."
            )

        if program == "prasarana":
            reminders.extend(
                [
                    "Juknis Prasarana mensyaratkan satuan pendidikan terdaftar pada Kementerian, aktif menyelenggarakan pendidikan, terdaftar pada EMIS, dan memiliki nomor statistik.",
                    "Cocokkan legalitas dengan jenis satuan pendidikan: Piagam Statistik/Piagam Tanda Daftar/Izin Pendirian dan/atau Izin Operasional yang relevan dan masih berlaku.",
                ]
            )

        if program == "kemitraan" and ("pslpq" in name or "psmdt" in name):
            reminders.append(
                "Perhatian: sasaran Juknis Kemitraan yang tercantum adalah Pesantren, Ormas Islam, AFPSPP, dan LSM; LPQ/MDT tidak disebut sebagai sasaran Kemitraan."
            )

    # --------------------------------------------------------
    # SK Kepengurusan
    # --------------------------------------------------------
    elif (
        "surat keputusan kepengurusan" in name
        or "sk kepengurusan" in name
        or "keputusan kepengurusan" in name
    ):
        reminders.extend(
            [
                "Periksa bahwa dokumen benar-benar berbentuk Surat Keputusan yang utuh, bukan hanya daftar/susunan pengurus.",
                "Periksa konsideran (misalnya Menimbang/Mengingat) serta diktum/amar keputusan (MEMUTUSKAN/Menetapkan, KESATU/KEDUA, dan seterusnya).",
                "Pastikan nama organisasi, pejabat/organ penerbit, dan periode kepengurusan konsisten serta masih berlaku.",
            ]
        )

        if program == "kemitraan":
            reminders.append(
                "Pada Juknis Kemitraan, Ormas Islam dan AFPSPP dibuktikan dengan Surat Keputusan Kepengurusan yang sah dan masih berlaku."
            )
        elif program == "halaqah":
            reminders.append(
                "Pada Juknis Halaqah, SK Kepengurusan merupakan bukti penting bagi Ormas Islam dan AFPSPP."
            )

    # --------------------------------------------------------
    # Akta Notaris
    # --------------------------------------------------------
    elif "akta notaris" in name:
        reminders.extend(
            [
                "Cocokkan nama badan/yayasan/LSM pada Akta dengan identitas pemohon dan dokumen badan hukum.",
                "Periksa nomor/tanggal akta, nama badan, pendiri/pengurus yang relevan, dan keterhubungan dengan lembaga pemohon.",
            ]
        )

        if program == "kemitraan":
            reminders.append(
                "Pada Juknis Kemitraan, LSM dibuktikan dengan akta notaris dan/atau badan hukum dari Kementerian Hukum dan HAM."
            )
        elif program == "halaqah":
            reminders.append(
                "Untuk LPQ/TPQ/MDT/Pesantren, Akta Notaris bukan otomatis menjadi syarat universal hanya karena slot SIMBA tersedia; nilai relevansinya sesuai jenis pemohon."
            )

    # --------------------------------------------------------
    # Badan Hukum Kemenkumham
    # --------------------------------------------------------
    elif (
        "badan hukum" in name
        or "kemenkumham" in name
        or "kementerian hukum" in name
    ):
        reminders.extend(
            [
                "Pastikan nama badan hukum, nomor/tanggal keputusan, dan nama pada Akta/identitas pemohon konsisten.",
                "Pastikan dokumen berasal dari instansi berwenang di bidang hukum dan dapat dibaca dengan jelas.",
            ]
        )

        if program == "kemitraan":
            reminders.append(
                "Juknis Kemitraan meminta salinan Surat Badan Hukum Kementerian Hukum bagi Ormas Islam, AFPSPP, atau LSM yang memiliki Badan Hukum."
            )
        elif program == "halaqah":
            reminders.append(
                "Pada Juknis Halaqah, Badan Hukum Kementerian Hukum berlaku bagi Ormas/AFPSPP/LSM yang berstatus berbadan hukum; bukan syarat universal LPQ/MDT/Pesantren."
            )

    # --------------------------------------------------------
    # SKT Kemendagri
    # --------------------------------------------------------
    elif (
        "surat keterangan terdaftar" in name
        or "surat tanda terdaftar" in name
        or name == "skt"
        or " skt " in f" {name} "
    ):
        if program == "halaqah":
            reminders.append(
                "Pada Juknis Halaqah, SKT Kemendagri yang masih berlaku digunakan bagi Ormas/AFPSPP/LSM yang tidak memiliki Badan Hukum."
            )
        elif program == "kemitraan":
            reminders.append(
                "Juknis Kemitraan yang menjadi acuan aplikasi tidak mencantumkan SKT Kemendagri sebagai lampiran proposal utama. Jangan menjadikannya alasan tunggal penolakan bila legalitas yang dipersyaratkan Juknis telah terpenuhi."
            )
        else:
            reminders.append(
                "Periksa relevansi SKT dengan jenis pemohon dan Juknis program; jangan memperlakukannya sebagai syarat universal."
            )

        reminders.append(
            "Jika SKT digunakan, periksa nama organisasi, nomor, instansi penerbit, dan masa berlaku dokumen."
        )

    # --------------------------------------------------------
    # Rencana Kegiatan / Program Kerja
    # --------------------------------------------------------
    elif (
        "rencana kegiatan" in name
        or "rencana program kerja" in name
        or "program kerja" in name
    ):
        if program == "halaqah":
            reminders.append(
                "Rencana Kegiatan Halaqah harus memuat: tujuan, sasaran, rangkaian kegiatan, hasil langsung (output), dan dampak (outcome) yang diharapkan."
            )
        elif program == "kemitraan":
            reminders.append(
                "Juknis Kemitraan mewajibkan Rencana Program Kerja sekurang-kurangnya memuat: Tujuan, Sasaran, Rangkaian Kegiatan, hasil langsung (output), dan dampak (outcome) yang ditargetkan."
            )
        else:
            reminders.append(
                "Pastikan rencana kegiatan menjelaskan tujuan, sasaran, tahapan/rangkaian, hasil yang ditargetkan, dan konsisten dengan RAB."
            )

    # --------------------------------------------------------
    # Profil
    # --------------------------------------------------------
    elif "profil" in name:
        if program == "kemitraan":
            if "lsm" in name:
                reminders.append(
                    "Profil LSM Kemitraan sekurang-kurangnya memuat sejarah/latar belakang berdiri, pendiri dan/atau pimpinan, bidang garapan, serta unit usaha bila ada."
                )
            elif "ormas" in name or "afpspp" in name:
                reminders.append(
                    "Profil Ormas Islam/AFPSPP Kemitraan sekurang-kurangnya memuat sejarah/latar belakang berdiri, pendiri dan/atau pimpinan, jumlah anggota, serta unit usaha bila ada."
                )
            elif "pesantren" in name:
                reminders.append(
                    "Profil Pesantren Kemitraan sekurang-kurangnya memuat sejarah/latar belakang berdiri, pendiri dan/atau pimpinan, jumlah anggota, serta unit usaha bila ada."
                )
            else:
                reminders.append(
                    "Sesuaikan isi profil dengan jenis pemohon Kemitraan: Pesantren, Ormas Islam, AFPSPP, atau LSM."
                )

        elif program == "prasarana":
            reminders.append(
                "Profil Prasarana harus disesuaikan dengan jenis pemohon. Untuk Pesantren periksa sejarah, pendiri/pengasuh, santri, satuan pendidikan, takhassus/kekhususan, dan unit usaha bila ada; untuk satuan pendidikan keagamaan Islam periksa sejarah, pendiri/pimpinan, santri, kekhususan, dan unit usaha bila ada."
            )
        else:
            reminders.append(
                "Sesuaikan isi profil dengan jenis pemohon dan pastikan nama, alamat, pimpinan, serta identitas lembaga konsisten dengan SIMBA."
            )

    # --------------------------------------------------------
    # Rekomendasi
    # --------------------------------------------------------
    elif "rekomendasi" in name:
        reminders.extend([
            "Pastikan rekomendasi menyebut lembaga pemohon yang benar dan secara eksplisit menyatakan keberadaan, keaktifan, serta kelayakan sebagai penerima bantuan.",
            "Periksa instansi penerbit, nomor/tanggal surat, pejabat penandatangan, dan keterkaitannya dengan program bantuan yang diajukan.",
            "Pengingat operasional verval: Surat Rekomendasi diarahkan kepada Yth. Direktur Jenderal Pendidikan Islam, c.q. Direktur Pesantren, di Jakarta. Karena Juknis tidak menyediakan contoh Surat Rekomendasi sejelas Surat Permohonan, catatan tujuan ini diperlakukan sebagai format operasional pemeriksaan.",
        ])
        if program == "halaqah":
            reminders.extend([
                "Juknis Halaqah mensyaratkan rekomendasi dari Kanwil Kementerian Agama dan/atau Kantor Kementerian Agama Kabupaten/Kota.",
                "Juknis tidak memberikan contoh format khusus Surat Rekomendasi. Untuk konsistensi administrasi, bila rekomendasi mencantumkan tujuan surat, dapat diarahkan kepada pemberi bantuan: Direktur Jenderal Pendidikan Islam Kementerian Agama c.q. Direktur Pesantren. Perbedaan tata letak bukan alasan tunggal penolakan.",
            ])
        elif program == "kemitraan":
            reminders.extend([
                "Juknis Kemitraan mensyaratkan rekomendasi dari Kanwil Kementerian Agama provinsi dan/atau Kantor Kementerian Agama Kabupaten/Kota.",
                "Juknis Kemitraan tidak memberikan contoh format khusus Surat Rekomendasi. Bila tujuan surat dicantumkan, pastikan konsisten dengan mekanisme pengajuan kepada Kementerian Agama c.q. Direktorat Pendidikan Islam.",
            ])
        elif program == "prasarana":
            reminders.extend([
                "Persyaratan penerima Prasarana memuat rekomendasi dari Kantor Kementerian Agama Kabupaten/Kota yang menyatakan keberadaan, keaktifan, dan kelayakan.",
                "Juknis tidak memberikan contoh format khusus Surat Rekomendasi. Untuk konsistensi administrasi, bila rekomendasi mencantumkan tujuan surat, dapat diarahkan kepada pemberi bantuan: Direktur Jenderal Pendidikan Islam Kementerian Agama c.q. Direktur Pesantren.",
            ])

    # --------------------------------------------------------
    # Rekening
    # --------------------------------------------------------
    elif "rekening" in name or "buku tabungan" in name:
        reminders.append(
            "Pastikan rekening/buku tabungan atas nama calon penerima/lembaga yang sah, nomor rekening dan nama bank terbaca, serta konsisten dengan data SIMBA."
        )

        if program == "kemitraan":
            reminders.append(
                "Pada Juknis Kemitraan, salinan buku tabungan/rekening bank atas nama calon penerima merupakan bagian dari dokumen pengajuan proposal."
            )
        elif program == "prasarana":
            reminders.append(
                "Pada Juknis Prasarana, salinan buku tabungan/rekening bank atas nama lembaga penerima merupakan bagian dari dokumen pengajuan proposal."
            )
        elif program == "halaqah":
            reminders.append(
                "Pada Juknis Halaqah, rekening berkaitan dengan administrasi pencairan; bedakan kelengkapan pencairan dari syarat substantif proposal awal."
            )

    # --------------------------------------------------------
    # NPWP
    # --------------------------------------------------------
    elif "npwp" in name or "nomor pokok wajib pajak" in name:
        reminders.append(
            "Pastikan NPWP atas nama calon penerima/lembaga yang sah dan identitasnya konsisten dengan SIMBA serta dokumen legalitas."
        )

        if program == "kemitraan":
            reminders.append(
                "Pada Juknis Kemitraan, salinan NPWP atas nama calon penerima merupakan bagian dari dokumen pengajuan proposal."
            )
        elif program == "prasarana":
            reminders.append(
                "Pada Juknis Prasarana, salinan NPWP atas nama lembaga penerima merupakan bagian dari dokumen pengajuan proposal."
            )
        elif program == "halaqah":
            reminders.append(
                "Pada Juknis Halaqah, NPWP muncul pada administrasi pencairan; bedakan kelengkapan pencairan dari syarat substantif proposal awal."
            )

    # --------------------------------------------------------
    # Prasarana: kepemilikan lahan
    # --------------------------------------------------------
    elif "kepemilikan lahan" in name or "hak atas lahan" in name:
        reminders.extend(
            [
                "Juknis Prasarana mensyaratkan dokumen kepemilikan/hak atas lahan dan lahan tidak dalam status sengketa.",
                "Cocokkan nama pemilik/pemegang hak, lokasi lahan, dan keterhubungannya dengan lembaga serta lokasi pekerjaan yang diajukan.",
            ]
        )

    # --------------------------------------------------------
    # Prasarana: dokumentasi/foto
    # --------------------------------------------------------
    elif (
        "foto kondisi lahan" in name
        or "dokumentasi kondisi lahan" in name
        or "foto lahan" in name
    ):
        reminders.extend(
            [
                "Khusus pembangunan: Juknis Prasarana meminta dokumentasi/foto kondisi lahan yang menunjukkan lokasi dan ukuran sebelum pekerjaan dilaksanakan.",
                "Periksa kecukupan sudut foto; Juknis menyebut dokumentasi minimal 5 sudut untuk pengajuan pembangunan.",
            ]
        )

    elif (
        "foto kondisi bangunan" in name
        or "dokumentasi kondisi bangunan" in name
        or "foto bangunan" in name
    ):
        reminders.extend(
            [
                "Khusus rehabilitasi: dokumentasi/foto harus menunjukkan kondisi bangunan, ukuran/luas bagian yang akan direhabilitasi, dan kondisi sebelum pekerjaan.",
                "Cocokkan kondisi pada foto dengan pekerjaan dan volume pada RAB.",
            ]
        )

    # --------------------------------------------------------
    # Prasarana: UPK2
    # --------------------------------------------------------
    elif "upk2" in name or "unit pengelola kegiatan" in name:
        reminders.append(
            "Juknis Prasarana mensyaratkan satuan pendidikan memiliki UPK2 yang dibuktikan dengan SK pimpinan lembaga; periksa susunan dan jumlah personel sesuai ketentuan Juknis."
        )

    # --------------------------------------------------------
    # Tema Halaqah
    # --------------------------------------------------------
    elif "tema" in name and "halaqah" in name:
        reminders.append(
            "Tema bukan pengganti Rencana Kegiatan Halaqah. Pastikan tema konsisten dengan tujuan, sasaran, rangkaian kegiatan, output/outcome, dan RAB."
        )

    # --------------------------------------------------------
    # Generic fallback agar setiap dokumen memiliki pengingat.
    # --------------------------------------------------------
    if not reminders:
        reminders.append(
            "Periksa kesesuaian nama/identitas lembaga, nomor dan tanggal dokumen, pihak penandatangan/penerbit, masa berlaku bila ada, serta konsistensinya dengan SIMBA, Juknis program, dan dokumen proposal lainnya."
        )

    if program == "prasarana":
        reminders.insert(
            0,
            "Bantuan Prasarana TA 2026 bernilai Rp100.000.000 berdasarkan surat pemberitahuan dan diperuntukkan bagi lembaga dengan kriteria khusus."
        )

    if program == "kemitraan":
        reminders.insert(
            0,
            "Bantuan Kemitraan TA 2026 bernilai Rp100.000.000 berdasarkan surat pemberitahuan. Sasaran Juknis: Pesantren, Ormas Islam, AFPSPP, atau LSM."
        )

    if program == "halaqah":
        reminders.insert(
            0,
            "Bantuan Halaqah TA 2026 bernilai Rp50.000.000 berdasarkan surat pemberitahuan."
        )

    return reminders

def make_document_key(document) -> str:
    raw = str(
        getattr(document, "id", "")
        or getattr(document, "category_id", "")
        or getattr(document, "name", "")
        or "document"
    )
    return normalize_name(raw).replace(" ", "-") or "document"


def default_document_review(document) -> dict:
    return {
        "status": STATUS_NOT_REVIEWED,
        "issues": [],
        "note": "",
        "updated_at": "",
    }


def _blank_state(application_id: str) -> dict:
    return {
        "application_id": str(application_id),
        "documents": {},
        "updated_at": "",
    }


class LocalReviewStore:
    """Penyimpanan lokal progres verval yang sederhana dan atomik."""

    def __init__(self, path: str | Path = "data/verval_state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> dict:
        if not self.path.exists():
            return {"applications": {}}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"applications": {}}
        if not isinstance(payload, dict):
            return {"applications": {}}
        payload.setdefault("applications", {})
        return payload

    def _write_all(self, payload: dict) -> None:
        fd, temp_name = tempfile.mkstemp(
            prefix="verval_state_",
            suffix=".json",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def get_application(self, application_id: str) -> dict:
        payload = self._read_all()
        app_id = str(application_id)
        state = payload["applications"].get(app_id)
        if not isinstance(state, dict):
            state = _blank_state(app_id)
        state.setdefault("documents", {})
        return state

    def save_application(self, application_id: str, state: dict) -> None:
        payload = self._read_all()
        app_id = str(application_id)
        state = dict(state)
        state["application_id"] = app_id
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        payload["applications"][app_id] = state
        self._write_all(payload)

    def ensure_documents(self, application_id: str, documents: Iterable) -> dict:
        state = self.get_application(application_id)
        changed = False
        for document in documents:
            key = make_document_key(document)
            current = state["documents"].get(key)
            if not isinstance(current, dict):
                state["documents"][key] = default_document_review(document)
                changed = True
                continue

            # Migrasi data dari versi lama: Tidak Sesuai -> Perlu Perbaikan.
            if current.get("status") == LEGACY_STATUS_INVALID:
                current["status"] = STATUS_REVISION
                changed = True

            current.setdefault("status", STATUS_NOT_REVIEWED)
            current.setdefault("issues", [])
            current.setdefault("note", "")
            current.setdefault("updated_at", "")

            # Pertahankan temuan yang sudah disimpan. Sejak V8 checklist
            # dapat berbeda menurut program bantuan, sehingga filtering
            # menggunakan aturan generik berisiko menghapus temuan yang sah.
            old_issues = list(current.get("issues") or [])
            cleaned_issues = [
                str(item).strip()
                for item in old_issues
                if str(item).strip()
            ]
            if cleaned_issues != old_issues:
                current["issues"] = cleaned_issues
                changed = True

        if changed:
            self.save_application(application_id, state)
        return state

    def save_document_review(
        self,
        application_id: str,
        document,
        *,
        status: str,
        issues: list[str] | None = None,
        note: str = "",
        **_legacy,
    ) -> dict:
        if status == LEGACY_STATUS_INVALID:
            status = STATUS_REVISION
        if status not in {STATUS_NOT_REVIEWED, STATUS_OK, STATUS_REVISION}:
            status = STATUS_NOT_REVIEWED

        state = self.get_application(application_id)
        key = make_document_key(document)
        # Temuan berasal dari checkbox UI program-aware. Simpan teks
        # non-kosong apa adanya agar tidak terhapus saat aturan berbeda
        # antara Halaqah/Kemitraan/Prasarana.
        valid_issues = [
            str(item).strip()
            for item in (issues or [])
            if str(item).strip()
        ]

        if status == STATUS_REVISION and not valid_issues and not (note or "").strip():
            raise ValueError(
                "Perlu Perbaikan harus memiliki minimal satu temuan atau catatan tambahan."
            )

        state["documents"][key] = {
            "status": status,
            "issues": valid_issues if status == STATUS_REVISION else [],
            "note": (note or "").strip() if status == STATUS_REVISION else "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.save_application(application_id, state)
        return state

    def clear_application(self, application_id: str) -> None:
        payload = self._read_all()
        payload["applications"].pop(str(application_id), None)
        self._write_all(payload)


def summarize_reviews(state: dict, documents: Iterable) -> dict:
    documents = list(documents)
    reviews = state.get("documents", {}) if isinstance(state, dict) else {}
    counts = {
        STATUS_NOT_REVIEWED: 0,
        STATUS_OK: 0,
        STATUS_REVISION: 0,
    }
    issues = []

    for document in documents:
        key = make_document_key(document)
        review = reviews.get(key) or default_document_review(document)
        status = review.get("status", STATUS_NOT_REVIEWED)
        if status == LEGACY_STATUS_INVALID:
            status = STATUS_REVISION
        if status not in counts:
            status = STATUS_NOT_REVIEWED
        counts[status] += 1
        if status == STATUS_REVISION:
            issues.append({
                "document_key": key,
                "document_name": str(getattr(document, "name", "") or "Dokumen"),
                "status": STATUS_REVISION,
                "issues": list(review.get("issues") or []),
                "note": (review.get("note") or "").strip(),
            })

    reviewed = len(documents) - counts[STATUS_NOT_REVIEWED]
    all_documents_reviewed = bool(documents) and reviewed == len(documents)
    all_documents_ok = bool(documents) and counts[STATUS_OK] == len(documents)

    return {
        "total": len(documents),
        "reviewed": reviewed,
        "counts": counts,
        "issues": issues,
        "all_documents_reviewed": all_documents_reviewed,
        "all_documents_ok": all_documents_ok,
        "ready_to_approve": all_documents_ok,
    }


def build_revision_note(summary: dict) -> str:
    lines = []
    for index, issue in enumerate(summary.get("issues", []), start=1):
        lines.append(f"{index}. {issue['document_name']}")
        for item in issue.get("issues", []):
            lines.append(f"   - {item}")
        if issue.get("note"):
            lines.append(f"   - Catatan: {issue['note']}")
    if not lines:
        return ""
    return "Mohon dilakukan perbaikan terhadap dokumen berikut:\n\n" + "\n".join(lines)
