# Panduan Deploy GitHub + Streamlit

## 1. Pastikan struktur root

File berikut harus ada di root repository:

```text
app.py
requirements.txt
runtime.txt
config.yaml
services/
utils/
.streamlit/config.toml
```

## 2. Jangan upload secret

File yang **tidak boleh** masuk GitHub:

```text
.streamlit/secrets.toml
.env
data/*.json
```

`.gitignore` pada project sudah mengaturnya.

## 3. Push ke GitHub

```powershell
git init
git add .
git commit -m "Release V8"
git branch -M main
git remote add origin https://github.com/USERNAME/NAMA-REPO.git
git push -u origin main
```

## 4. Streamlit Community Cloud

- Repository: repository project Anda.
- Branch: `main`.
- Main file: `app.py`.
- Python: 3.12.
- Secrets:

```toml
APP_PASSWORD = "gunakan-password-kuat"
```

Tidak perlu memasukkan Cookie SIMBA ke Secrets.

## 5. Setelah deploy

1. Buka URL aplikasi.
2. Masukkan APP_PASSWORD.
3. Tempel Cookie Session SIMBA di sidebar.
4. Mulai dengan `DRY RUN`.
5. Setelah endpoint/form terbaca benar, gunakan `LIVE SIMBA` hanya untuk proposal yang benar.

## 6. Update aplikasi

Setelah mengubah code lokal:

```powershell
git status
git add .
git commit -m "Penyempurnaan verval"
git push
```

Streamlit Community Cloud akan redeploy dari branch GitHub.


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
