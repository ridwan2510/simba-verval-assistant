# Pemetaan Checklist Juknis — Bantuan Halaqah TA 2026

Aplikasi ini memetakan checklist kerja verifikator berdasarkan **Keputusan Direktur Jenderal Pendidikan Islam Nomor 6301 Tahun 2026 tentang Petunjuk Teknis Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam**.

Fokus pemetaan:
- Bab II bagian persyaratan penerima bantuan dan pengajuan/seleksi penerima.
- Dokumen: surat permohonan, PSP/izin/SKT, akta notaris/badan hukum, SK kepengurusan, rencana kegiatan, RAB, profil lembaga, rekomendasi Kabupaten/Kota.
- Dokumen rekening dan NPWP ditampilkan sebagai pengecekan administrasi karena tersedia pada alur SIMBA dan relevan pada kelengkapan pencairan.
- RAB diperiksa terhadap format/struktur, keterkaitan dengan kegiatan Halaqah, konsistensi perhitungan, pelaksanaan dalam tahun anggaran, serta larangan penggunaan di luar Juknis/bertentangan dengan peraturan.

## Prinsip aplikasi

Checklist **tidak mengklaim membaca dan memutuskan isi PDF secara otomatis**. Jenis checklist dipilih otomatis dari nama dokumen, rekap dan catatan perbaikan dibentuk otomatis, tetapi verifikator tetap mencentang hasil pemeriksaan setelah membaca berkas.

Status per dokumen:
- Belum diperiksa
- Sesuai
- Perlu Perbaikan
- Tidak Sesuai

Jika status `Sesuai`, seluruh butir checklist harus terpenuhi.

## Keputusan otomatis yang disarankan

- Semua dokumen `Sesuai` + checklist kelayakan umum lengkap → saran `Verifikasi Proposal`.
- Ada temuan pada Surat Rekomendasi Kabupaten → saran `Tolak/Revisi → Kabupaten`.
- Ada temuan dokumen lain → saran `Tolak/Revisi → Lembaga`.

Saran ini tidak mengubah SIMBA dan masih dapat ditinjau oleh verifikator.

## Keamanan

Versi ini tetap **DRY RUN** dan tidak mempunyai POST verifikasi live ke SIMBA. Jangan menambahkan endpoint POST berdasarkan tebakan. Aktivasi verifikasi live baru dilakukan setelah Request URL, Method, field Payload/Form Data, mekanisme CSRF, response, dan status sesudah submit telah dipetakan dari request SIMBA asli.


## Sumber tambahan — Surat Pemberitahuan TA 2026

Versi V7.4 juga menggunakan Surat Direktur Pesantren Nomor B-35/Dt.I.V/HM.01/09/2026 tanggal 1 September 2026 untuk pengingat nominal program:
- Kemitraan Pesantren dan Pendidikan Keagamaan Islam: Rp100.000.000.
- Bantuan Halaqah Pesantren dan Pendidikan Keagamaan Islam: Rp50.000.000.
- Bantuan Prasarana Pesantren dan Pendidikan Keagamaan Islam: Rp100.000.000, untuk lembaga dengan kriteria khusus.

Catatan masa berlaku izin 5 tahun ditampilkan sebagai **pengingat kerja verifikator**, bukan keputusan otomatis. Aplikasi tidak menghitung masa berlaku dari tanggal upload; verifikator harus membaca tanggal terbit/masa berlaku pada dokumen.

## Pengingat per jenis legalitas

- Pesantren: PSP dan NSPP harus konsisten.
- LPQ/TPQ: PSLPQ/izin atau registrasi yang relevan harus konsisten dan masih berlaku.
- MDT: PSMDT/izin atau registrasi yang relevan harus konsisten dan masih berlaku.
- Ormas Islam/AFPSPP: periksa SK Kepengurusan yang sah dan masih berlaku; bila tidak berbadan hukum periksa SKT, bila berbadan hukum periksa dokumen badan hukum sesuai Juknis program.
- LSM/badan lain: periksa Akta/Badan Hukum/SKT sesuai status hukumnya, dan jangan menyamakan syarat tersebut untuk semua jenis lembaga.
