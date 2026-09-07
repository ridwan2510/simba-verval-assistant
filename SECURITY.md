# Security Notes

Aplikasi ini berinteraksi dengan SIMBA menggunakan session milik petugas.

## Jangan pernah masukkan ke repository

- Cookie SIMBA
- Password SIMBA
- XSRF/CSRF token
- Authorization header
- Session ID
- `.streamlit/secrets.toml`
- `.env`

## Streamlit Cloud

Untuk deployment internet/public, aktifkan:

```toml
APP_PASSWORD = "password-kuat"
```

melalui Streamlit App Settings > Secrets.

`APP_PASSWORD` hanya melindungi pintu masuk aplikasi. Hak akses tindakan pada
SIMBA tetap mengikuti session SIMBA yang ditempel oleh petugas.

## Runtime state

Review state dan submission log dibuat berdasarkan hash session SIMBA. Nilai
Cookie asli tidak ditulis ke nama file. File runtime `data/*.json` tidak
dikomit ke GitHub dan pada Streamlit Cloud dapat hilang ketika instance restart.

## LIVE mode

- Default tetap DRY RUN.
- LIVE hanya memakai form/action/field/value yang ditemukan dari halaman SIMBA.
- Tidak melakukan blind retry setelah status ambigu.
- Tolak → Kabupaten diblokir sampai request asli dapat dibedakan secara aman.


## V8.1 Tolak → Kabupaten
UI aktif secara dinamis. Tidak ada payload hardcode/tebakan. LIVE hanya berjalan bila form POST Kabupaten yang asli ditemukan dan fingerprint-nya berbeda dari Tolak → Lembaga.


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


## V8.1.5 — Streamlit Community Cloud Fix

Perbaikan deployment cloud:

- Request URL DataTables yang dicopy dari DevTools otomatis dibersihkan dari
  `draw`, `start`, `length`, `columns[...]`, `order[...]`, `search[...]`, dan `_`.
  Ini mencegah filter pencarian lama ikut terbawa (contoh: `145 total / 2 filtered`).
- Daftar lembaga diambil bertahap maksimal 50 record per request agar respons
  SIMBA lebih ringan dan lebih stabil dari Streamlit Community Cloud.
- Endpoint DataTables boleh retry satu kali khusus jika timeout karena endpoint
  tersebut hanya membaca data.
- Jika load baru gagal, daftar/metric lama dibersihkan sehingga angka lama tidak
  terlihat sebagai hasil request yang baru.
- LIVE POST verifikasi tidak mendapat auto-retry dan pengaman lama tetap aktif.


## V8.1.6 — LAN Performance

Optimasi untuk penggunaan dari komputer lokal/LAN:

- Streamlit tidak lagi mengambil ulang profil, link detail, kelengkapan, dan daftar
  dokumen dari SIMBA pada setiap `st.rerun()`. Data proposal disimpan pada
  `st.session_state` per browser selama 10 menit.
- Form LIVE untuk tampilan di-cache 60 detik. **Saat benar-benar POST,
  `submit_once()` tetap mengambil form dan CSRF terbaru**, jadi pengaman LIVE tidak
  dikurangi.
- HTML halaman detail dipakai ulang untuk membaca profil sehingga tidak perlu GET
  detail kedua.
- HTML halaman Review Proposal dipakai ulang untuk kelengkapan dan discovery AJAX.
- Daftar dokumen diminta dengan `length=100`, bukan 500.
- Cache PDF dibersihkan ketika berpindah lembaga agar RAM komputer server tidak
  terus membesar.
- Tombol `Refresh Proposal` disediakan bila pengguna ingin memaksa mengambil data
  terbaru dari SIMBA.
- Mengganti Cookie Session otomatis membuang data/cache sesi sebelumnya.


## V8.1.7 — GET Recheck Tolak → Lembaga

- Jika POST sudah HTTP 200 tetapi hasil belum terkonfirmasi, POST ulang tetap diblokir.
- Ada tombol **Periksa Ulang Hasil SIMBA (GET saja)** yang tidak mengirim keputusan baru.
- Lookup hasil Kanwil mencoba application ID, NSPP, nama lembaga, lalu scan endpoint tanpa filter.
- Parameter DataTables lama tidak dipakai untuk verifikasi pasca-POST.
- Untuk Tolak → Lembaga, bukti ideal: ID sama, status `Ditolak Kanwil`,
  dan bukti tujuan/catatan `Catatan kanwil ke lembaga`.
