# SIMBA Verval Assistant V8.1

Asisten Streamlit untuk membantu pemeriksaan proposal bantuan SIMBA dengan
checklist temuan negatif, pengingat dokumen, preview PDF, DRY RUN, dan
pengiriman LIVE yang dibatasi oleh pengaman form discovery.

## Program TA 2026 yang dipetakan

| Program | Nominal |
|---|---:|
| Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam | Rp50.000.000 |
| Bantuan Kemitraan Pesantren dan Pendidikan Keagamaan Islam | Rp100.000.000 |
| Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam | Rp100.000.000 |

Nominal mengikuti Surat Pemberitahuan Pengajuan Bantuan TA 2026. Checklist dan
pengingat dokumen menyesuaikan Juknis masing-masing program.

## Fitur

- Membaca daftar lembaga SIMBA melalui AJAX DataTables.
- Auto-discovery detail pengajuan dan Review Proposal.
- Preview PDF dan dokumen TEXT.
- Status dokumen: `Sesuai` / `Perlu Perbaikan`.
- Checklist temuan negatif menurut jenis dokumen dan program bantuan.
- Kotak **Pengingat Verval** merah muda pada setiap dokumen.
- Nominal RAB otomatis sesuai program.
- Reminder masa berlaku Izin Operasional/Izin Pendirian.
- Aturan legalitas Pesantren, LPQ/MDT, Ormas Islam, AFPSPP, dan LSM.
- Prasarana: reminder kepemilikan lahan, foto pembangunan/rehabilitasi, dan UPK2.
- Kemitraan: reminder sasaran, legalitas, Rencana Program Kerja, rekening, NPWP, dan profil.
- Auto-next setelah verifikasi/penolakan sukses.
- LIVE SIMBA hanya bila struktur form asli berhasil dikenali.
- Tolak → Kabupaten tetap diblokir sampai request asli SIMBA dapat dipetakan dengan aman.
- Review state dan submission guard diisolasi berdasarkan session SIMBA.

## Jalankan Lokal

```powershell
cd D:\Project\python\simba_verval_assistant

python -m venv venv
.\venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m streamlit run app.py
```

## Upload ke GitHub

Buka PowerShell di folder project:

```powershell
git init
git add .
git commit -m "Release SIMBA Verval Assistant V8"
git branch -M main
git remote add origin https://github.com/USERNAME/NAMA-REPO.git
git push -u origin main
```

Untuk update berikutnya:

```powershell
git add .
git commit -m "Update aplikasi"
git push
```

## Deploy ke Streamlit Community Cloud

1. Push project ini ke GitHub.
2. Buka Streamlit Community Cloud.
3. Pilih **Create app / New app**.
4. Pilih repository GitHub.
5. Branch: `main`.
6. Main file path: `app.py`.
7. Gunakan Python **3.12** bila diminta memilih versi.
8. Pada **App settings > Secrets**, isi:

```toml
APP_PASSWORD = "password-aplikasi-yang-kuat"
```

9. Deploy.

`APP_PASSWORD` sangat disarankan karena aplikasi menggunakan session SIMBA
milik petugas. File `.streamlit/secrets.toml` asli sudah di-ignore oleh Git.

## Keamanan

- **Jangan** commit Cookie SIMBA, password, token, XSRF/CSRF, Authorization,
  atau session ID ke GitHub.
- Cookie SIMBA **tidak** perlu dimasukkan ke Streamlit Secrets.
- Tempel Cookie hanya di UI pada saat sesi kerja.
- Setelah selesai, logout dari SIMBA bila diperlukan untuk memutus session.
- Untuk repository publik, aktifkan `APP_PASSWORD`.
- LIVE SIMBA adalah tindakan nyata. Uji dengan DRY RUN dan satu proposal lebih dulu.

Lihat `SECURITY.md` dan `DEPLOY_STREAMLIT.md`.


## V8.1 Latest
- Surat Permohonan Halaqah/Prasarana: cek tujuan surat sesuai contoh Juknis (Dirjen Pendis c.q. Direktur Pesantren, Di Jakarta).
- Surat Rekomendasi: cek asal instansi, nomor/tanggal, identitas, keberadaan, keaktifan, kelayakan, dan keterkaitan program.
- Tolak → Kabupaten tidak lagi di-hard-disable. Engine melakukan discovery GET-only dan mengaktifkan LIVE hanya bila kontrol/form asli SIMBA ditemukan serta berbeda dari jalur Lembaga.


## V8.1.1 Latest Fix

- Memperbaiki `NameError: form_inspection is not defined` saat memilih **Tolak → Kabupaten**.
- Status kesiapan jalur Kabupaten sekarang ditampilkan setelah inspeksi form SIMBA selesai.
- Jalur Kabupaten tetap dapat LIVE bila kontrol/form asli berhasil ditemukan dan fingerprint-nya berbeda dari jalur Lembaga.
- Jika SIMBA tidak menyediakan kontrol Kabupaten untuk proposal tertentu, POST tetap diblokir tanpa menebak payload.


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


## V8.1.4 — Tutorial Penggunaan di Halaman Awal

Halaman awal aplikasi sekarang memiliki tutorial bergambar untuk:
1. login ke SIMBA;
2. membuka menu Pengajuan;
3. membuka Inspect/Developer Tools;
4. memilih Network;
5. memilih Fetch/XHR;
6. membuka Headers dan menyalin Request URL;
7. membuka Cookies/Request Headers dan menyalin Cookie Session;
8. menempel Request URL + Cookie ke sidebar lalu Muat Data.

Screenshot Cookie yang disertakan di repository **sudah disamarkan**. Cookie/session
asli tidak disimpan dalam project, GitHub, README, maupun Streamlit Secrets.
