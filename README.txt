SIMBA VERVAL ASSISTANT - JUKNIS CHECKLIST / SAFE DRY RUN
=======================================================

Fitur utama:
1. Membaca daftar lembaga SIMBA melalui AJAX DataTables.
2. Profil lembaga, program bantuan, status dan identitas pengajuan.
3. Membaca daftar dokumen proposal otomatis.
4. Preview PDF langsung di Streamlit dan dokumen TEXT.
5. Menambahkan Surat Rekomendasi Kabupaten dari data daftar lembaga.
6. Checklist otomatis berdasarkan jenis dokumen sesuai pemetaan Juknis Halaqah TA 2026.
7. Status dokumen: Belum diperiksa / Sesuai / Perlu Perbaikan / Tidak Sesuai.
8. Tombol cepat "Tandai Dokumen Sesuai" untuk mempercepat verval setelah berkas dibaca.
9. Progres checklist disimpan lokal ke data/verval_state.json.
10. Rekap otomatis jumlah dokumen diperiksa/sesuai/perlu perbaikan/tidak sesuai.
11. Catatan revisi otomatis dibentuk dari butir checklist yang belum terpenuhi.
12. Saran otomatis: Verifikasi / kembalikan ke Lembaga / kembalikan ke Kabupaten.
13. Validasi target ID + NSPP + nama sebelum simulasi keputusan.
14. GET ulang target sesudah DRY RUN untuk memastikan proposal yang sama.
15. TIDAK ADA POST VERIFIKASI LIVE ke SIMBA.

INSTALL / UPDATE
----------------
Sebaiknya backup project lama lalu replace seluruh file project dengan isi ZIP ini,
tetapi pertahankan venv lama jika masih digunakan.

PowerShell:

cd D:\Project\python\simba_verval_assistant
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m py_compile app.py
python -m py_compile services\simba_client.py
python -m py_compile services\checklist_service.py
python -m py_compile utils\helpers.py
python -c "from services.simba_client import SimbaClient; from services.checklist_service import LocalReviewStore; print('IMPORT OK')"
python -m streamlit run app.py

PENTING
-------
- data/verval_state.json menyimpan progres checklist di komputer lokal.
- Jangan hapus file tersebut jika ingin melanjutkan progres pemeriksaan.
- Reset checklist dari UI hanya menghapus progres lokal proposal terkait.
- Versi ini belum mengirim keputusan ke server SIMBA.
- Jangan pernah membagikan Cookie, session, XSRF/CSRF token, Authorization, atau password.

VERSI V3 - CHECKLIST TEMUAN NEGATIF
------------------------------------
Checklist hanya muncul saat memilih Perlu Perbaikan.
Setiap checkbox sekarang menyatakan MASALAH/TEMUAN, misalnya:
- Dokumen tidak tersedia/tidak terbaca.
- Nama lembaga tidak konsisten.
- Nomor/tanggal dokumen tidak dapat diidentifikasi.
- Dokumen tidak ditandatangani.

Untuk menyimpan status Perlu Perbaikan, minimal satu temuan harus dicentang
atau Catatan Tambahan harus diisi.

VERSI V4 - QUICK REVIEW
-----------------------
- Tombol Sesuai: satu klik, langsung tersimpan dan pindah ke dokumen berikutnya.
- Tombol Perbaikan / Tidak Sesuai: membuka checklist temuan negatif dan catatan.
- Perbaikan disimpan melalui tombol Simpan Perbaikan & Dokumen Selanjutnya.
- Tombol Dokumen Selanjutnya tersedia untuk navigasi tanpa mengubah hasil.
- Tidak ada lagi tombol Simpan Hasil Dokumen untuk dokumen yang Sesuai.


NAVIGASI V5
-----------
- Nilai selectbox menggunakan document_key yang stabil, bukan index.
- Semua perpindahan memakai satu jalur pending_doc_key.
- Klik "Sesuai" menyimpan dan maju tepat 1 dokumen.
- Simpan Perbaikan menyimpan dan maju tepat 1 dokumen.
- Tombol "Dokumen Selanjutnya (tanpa mengubah status)" hanya maju tepat 1 dokumen.


VERSI V6 - LIVE READY
======================

Versi ini menambahkan mode LIVE SIMBA tanpa menebak endpoint/payload.

Cara kerja LIVE:
1. Aplikasi GET halaman "Hasil Verifikasi" milik proposal yang sedang dipilih.
2. Form HTML dibaca otomatis.
3. Action URL, method POST, hidden inputs, field keputusan, nilai radio/select,
   field catatan, dan CSRF dibaca dari halaman SIMBA saat itu.
4. Jika struktur form tidak dapat dikenali dengan aman, tombol LIVE diblokir.
5. Sebelum POST, aplikasi mengecek ulang nama lembaga + NSPP + target.
6. POST dilakukan SATU KALI.
7. Setelah POST, aplikasi mencari bukti status:
   - approve -> "Diverifikasi Kanwil"
   - reject  -> "Ditolak Kanwil"
8. Bila status belum terkonfirmasi, aplikasi tidak menganggap sukses dan
   Submission Guard memblokir POST kedua.

PENTING:
- Default UI tetap DRY RUN.
- Untuk mengirim nyata, pilih "LIVE SIMBA" pada sidebar.
- Uji satu proposal lebih dulu.
- Jangan mengirim Cookie/token/password kepada pihak lain.
- Bila LIVE mengatakan "struktur form tidak dikenali", jangan memaksa;
  ambil Request URL + Method + nama field dari DevTools Network.


V6.1 - TRANSITION ROUTE FIX
===========================
Perbaikan khusus setelah POST:
- 404 pada route lama /diverifikasikabupaten/... tidak langsung dianggap gagal.
- Bila proposal sudah pernah di-POST, aplikasi lebih dulu mencoba route
  /diproseskanwil/... dengan GET-only.
- Aplikasi tidak crash setelah status proposal berpindah.
- Submission Guard tetap memblokir POST kedua.
- Jangan mengirim ulang hanya karena route lama 404.


V6.2 - REJECT DESTINATION SAFETY
================================
- Tolak ke Lembaga dan Tolak ke Kabupaten harus mempunyai fingerprint
  request yang berbeda (action / field / value / control).
- Bila fingerprint keduanya identik, LIVE reject diblokir.
- Dialog konfirmasi menampilkan TUJUAN PENGEMBALIAN dengan jelas.
- Struktur request menampilkan label asli SIMBA + field + value.
- Status "Ditolak Kanwil" dipakai untuk membuktikan penolakan berhasil.
- Tujuan Lembaga/Kabupaten divalidasi dari kontrol form asli sebelum POST.


FINAL V7
========

Fokus versi final:
1. Review dokumen cepat:
   - Sesuai -> simpan otomatis + lanjut 1 dokumen.
   - Perbaikan/Tidak Sesuai -> checklist temuan negatif + catatan + lanjut.
2. Hasil verifikasi:
   - Verifikasi Proposal
   - Tolak -> Lembaga
   - Tolak -> Kabupaten
3. LIVE SIMBA:
   - Endpoint/payload tidak ditebak.
   - Form Hasil Verifikasi dibaca langsung dari SIMBA.
   - CSRF/hidden field dibaca ulang sebelum POST.
   - POST hanya sekali.
4. Submission Guard:
   - Mencegah double-submit.
5. Post-verification tiga lapis:
   - ID/NSPP/nama sama.
   - Status akhir benar.
   - Untuk reject, tujuan pengembalian dicari dari bukti eksplisit SIMBA.
6. Status target:
   - Approve -> Diverifikasi Kanwil.
   - Reject -> Ditolak Kanwil.
7. Bukti reject:
   - Tolak -> Lembaga dapat dikonfirmasi bila SIMBA mengembalikan label
     "Catatan kanwil ke lembaga" / "kanwil ke lembaga".
   - Tolak -> Kabupaten hanya dikonfirmasi bila SIMBA mengembalikan bukti
     eksplisit "kanwil ke kabupaten". Tidak ada tebakan.
8. Bila status sudah Ditolak Kanwil tetapi tujuan belum dapat dibuktikan:
   - Tidak mengirim ulang.
   - Menampilkan STATUS_CONFIRMED_DESTINATION_UNCONFIRMED.
9. Route transition:
   - /diverifikasikabupaten/ -> /diproseskanwil/ ditangani otomatis.
10. Jangan membagikan Cookie, token, session, Authorization, atau password.

FINAL V7.1 - ROBUST REJECT CONTROL
==================================
- Mengenali variasi label "Kembalikan ke Kabupaten" tanpa kata "Tolak".
- Membaca label dari sibling/wrapper/custom radio markup.
- Tetap memblokir LIVE bila jalur reject tidak dapat dibedakan.
- Menambahkan diagnostik kontrol form SIMBA tanpa token/cookie.

FINAL V7.2 SAFE LIVE
====================
Perubahan:
- Verifikasi Proposal: LIVE aktif bila form terdeteksi.
- Tolak -> Lembaga: LIVE aktif bila kontrol eksplisit SIMBA ditemukan.
  Data nyata: terima_tolak=tolak, label Kembalikan ke Lembaga.
- Tolak -> Kabupaten: LIVE tetap diblokir sampai request POST asli
  Kabupaten ditemukan. Tidak ada payload tebakan.
- Setelah POST, aplikasi GET endpoint:
  /wilayah/verifikasi/{aid}/diproseskanwil/data-index/{prov}/{kab}
  dan mencari ID pengajuan yang sama.
- Approve sukses jika status = Diverifikasi Kanwil.
- Tolak Lembaga sukses penuh jika status = Ditolak Kanwil DAN
  bukti "Catatan kanwil ke lembaga" terbaca.
- Route lama 404 setelah POST ditangani sebagai transisi status,
  bukan otomatis dianggap gagal.

FINAL V7.3 - AUTO NEXT + SK FORMAT
==================================
Penyempurnaan:
1. Checklist SK Kepengurusan:
   - dokumen hanya berupa daftar/susunan pengurus,
   - tidak ada konsideran (Menimbang/Mengingat),
   - tidak ada diktum/amar keputusan
     (MEMUTUSKAN/Menetapkan/KESATU/KEDUA/dst).
2. Setelah LIVE submit dan status sudah terkonfirmasi:
   - daftar Diverifikasi Kabupaten dimuat ulang otomatis,
   - proposal yang selesai dikeluarkan dari antrean lokal,
   - pencarian dan viewer lama direset,
   - aplikasi otomatis membuka proposal berikutnya.
3. Jika refresh antrean gagal, hasil POST tetap tidak dianggap gagal.
   Pengguna dapat memakai tombol Muat Data secara manual.


FINAL V7.4 - DOCUMENT REMINDER
================================
- Setiap dokumen menampilkan kotak PENGINGAT VERVAL berwarna merah muda.
- RAB menampilkan nominal program TA 2026 berdasarkan Surat B-35/Dt.I.V/HM.01/09/2026:
  * Kemitraan: Rp100.000.000
  * Halaqah: Rp50.000.000
  * Prasarana: Rp100.000.000 (lembaga dengan kriteria khusus)
- Dokumen izin menampilkan pengingat masa berlaku 5 tahun: jika sudah lewat 5 tahun/berakhir, minta pembaruan.
- Legalitas Ormas/AFPSPP/LSM dibedakan antara SK Kepengurusan, SKT Kemendagri, Akta Notaris, dan Badan Hukum.
- Akta/Badan Hukum tidak diperlakukan sebagai syarat universal LPQ/MDT/Pesantren hanya karena slot SIMBA tersedia.
- Pengingat tidak mengambil keputusan otomatis; verifikator tetap membaca dokumen dan Juknis program.

V8.0 - RELEASE READY
====================
- Juknis Halaqah + Kemitraan + Prasarana dipetakan ke checklist/pengingat.
- Checklist dokumen sekarang program-aware.
- Kemitraan: sasaran Pesantren/Ormas/AFPSPP/LSM; Rencana Program Kerja,
  rekening dan NPWP sebagai dokumen pengajuan; legalitas program-specific.
- Prasarana: izin/registrasi masih berlaku, lahan, foto pembangunan/rehab, UPK2.
- Pengingat izin 5 tahun dibuat kondisional: hanya jika dokumen memang menyatakan 5 tahun.
- Streamlit Cloud ready: README.md, DEPLOY_STREAMLIT.md, runtime.txt,
  .streamlit/config.toml, secrets example.
- Optional APP_PASSWORD untuk deployment publik.
- Runtime state diisolasi berdasarkan hash session SIMBA.
- Cookie/token tidak disimpan ke GitHub.


## V8.1.2 — Kabupaten Result Verified

Hasil nyata SIMBA untuk **Tolak → Kabupaten** sudah dipetakan:
- status akhir: `Ditolak kanwil ke kabupaten`;
- catatan: `Catatan kanwil ke kabupaten`;
- status dan tujuan dapat dikonfirmasi ulang melalui endpoint hasil Kanwil.

Catatan penting: bukti hasil ini memvalidasi **post-verification**, tetapi bukan
payload POST pengiriman. Aplikasi tetap tidak akan menebak POST Kabupaten jika
kontrol/request aslinya belum ditemukan pada halaman SIMBA.

Surat Rekomendasi juga mendapat pengingat operasional tujuan:
`Yth. Direktur Jenderal Pendidikan Islam, c.q. Direktur Pesantren, di Jakarta`.
Karena Juknis tidak menyediakan contoh Surat Rekomendasi sejelas Surat
Permohonan, keterangan tujuan tersebut ditandai sebagai format operasional verval.


## V8.1.3 — Kabupaten LIVE Verified

Jalur **Tolak → Kabupaten** sudah dapat digunakan LIVE berdasarkan request
Network asli SIMBA yang berhasil diverifikasi:

- Method: `POST`
- action: form `simpan-rekomendasi-wilayah/.../diverifikasikabupaten/...`
- field keputusan: `terima_tolak`
- nilai Kabupaten: `tolak_kabupaten`
- field catatan: `catatan_wilayah`
- tipe request: `multipart/form-data`
- input file kosong dari form tetap dikirim sebagai multipart part kosong.

Fallback LIVE hanya diaktifkan bila form runtime cocok dengan schema yang sudah
terverifikasi: approve `terima`, tolak Lembaga `tolak`, note field
`catatan_wilayah`, dan action route SIMBA yang sesuai. Jika schema berubah,
LIVE Kabupaten kembali diblokir daripada menebak.

Post-verification Kabupaten tetap memerlukan bukti server:
`Ditolak kanwil ke kabupaten` / `Catatan kanwil ke kabupaten`.
