from __future__ import annotations

import hashlib
import hmac
import html
from pathlib import Path

import streamlit as st
import yaml
from streamlit_pdf_viewer import pdf_viewer

from services.simba_client import (
    SimbaClient,
    SimbaError,
    ProposalDocument,
)
from services.checklist_service import (
    LocalReviewStore,
    STATUS_NOT_REVIEWED,
    STATUS_OK,
    STATUS_REVISION,
    get_rules_for_document,
    get_document_reminders,
    make_document_key,
    summarize_reviews,
    build_revision_note,
)
from services.live_verification import (
    VerificationFormEngine,
    SubmissionLog,
    LiveVerificationError,
)


st.set_page_config(
    page_title="SIMBA Verval Assistant",
    page_icon="📑",
    layout="wide",
)


def _secret_text(name: str) -> str:
    """Baca Streamlit secret secara aman bila tersedia."""
    try:
        return str(
            st.secrets.get(
                name,
                "",
            )
            or ""
        ).strip()
    except Exception:
        return ""


APP_PASSWORD = _secret_text(
    "APP_PASSWORD"
)


def enforce_app_password() -> None:
    """
    Password gate opsional untuk deployment Streamlit publik.

    Jika APP_PASSWORD tidak diset, aplikasi tetap bisa berjalan lokal.
    Untuk Streamlit Community Cloud sangat disarankan mengaktifkannya.
    """
    if not APP_PASSWORD:
        return

    if st.session_state.get(
        "_app_access_granted",
        False,
    ):
        return

    st.title(
        "🔐 SIMBA Verval Assistant"
    )

    st.caption(
        "Aplikasi ini dibatasi untuk petugas yang berwenang."
    )

    entered = st.text_input(
        "Kata sandi aplikasi",
        type="password",
        key="_app_password_input",
    )

    if entered:
        if hmac.compare_digest(
            entered,
            APP_PASSWORD,
        ):
            st.session_state[
                "_app_access_granted"
            ] = True
            st.rerun()

        st.error(
            "Kata sandi aplikasi tidak sesuai."
        )

    st.stop()


enforce_app_password()


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 100%;
    }

    div[data-testid="stSidebar"] {
        min-width: 300px;
    }

    .text-document {
        padding: 22px;
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 12px;
        background: rgba(128,128,128,.04);
        font-size: 1.05rem;
        line-height: 1.8;
        margin-top: 10px;
    }

    .doc-reminder {
        background: #fde8ee;
        border: 1px solid #f3b8c8;
        border-left: 6px solid #d94a70;
        border-radius: 12px;
        padding: 14px 16px;
        margin: 10px 0 18px 0;
        color: #6d263a;
        line-height: 1.55;
    }

    .doc-reminder strong {
        color: #8c2948;
    }

    .doc-reminder ul {
        margin: 8px 0 0 20px;
        padding: 0;
    }

    .doc-reminder li {
        margin-bottom: 5px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



def render_usage_tutorial(
    expanded: bool = False,
) -> None:
    """Tutorial memperoleh Request URL dan Cookie Session dari Chrome DevTools."""
    tutorial_dir = (
        Path(__file__).resolve().parent
        / "assets"
        / "tutorial"
    )

    with st.expander(
        "📘 Tutorial Penggunaan Aplikasi — Login SIMBA sampai Muat Data",
        expanded=expanded,
    ):
        st.markdown(
            """
            Tutorial ini digunakan untuk memperoleh **Request URL AJAX Lembaga**
            dan **Cookie Session** yang diperlukan aplikasi. Ikuti langkah secara
            berurutan pada browser Chrome/Chromium yang sudah login ke SIMBA.
            """
        )

        st.warning(
            "🔐 Cookie Session adalah kredensial sesi yang sensitif. "
            "Jangan mengirimkan Cookie ke orang lain, jangan memasukkannya ke "
            "GitHub, README, screenshot publik, atau Streamlit Secrets. "
            "Screenshot Cookie pada tutorial ini sudah disamarkan."
        )

        st.markdown("### 1. Login ke SIMBA")
        st.markdown(
            "Buka SIMBA pada browser dan **login menggunakan akun petugas yang "
            "berwenang**. Setelah berhasil masuk, tetap gunakan tab browser yang "
            "sama agar session/cookie yang diambil masih aktif."
        )

        st.markdown("### 2. Masuk ke daftar pengajuan")
        st.markdown(
            "Buka menu verifikasi/pengajuan yang akan diperiksa, lalu klik tombol "
            "**Pengajuan** sehingga daftar lembaga tampil."
        )
        img = tutorial_dir / "01_pengajuan.png"
        if img.exists():
            st.image(
                str(img),
                caption="Klik Pengajuan untuk membuka daftar proposal/lembaga.",
                width=520,
            )

        st.markdown("### 3. Buka Inspect / Developer Tools")
        st.markdown(
            "Klik kanan pada area halaman SIMBA, lalu pilih **Inspect**. "
            "Alternatifnya tekan **F12** atau **Ctrl+Shift+I**."
        )
        img = tutorial_dir / "02_inspect.png"
        if img.exists():
            st.image(
                str(img),
                caption="Klik kanan halaman → Inspect.",
                width=360,
            )

        st.markdown("### 4. Pilih tab Network")
        st.markdown(
            "Pada Developer Tools pilih tab **Network**. Jika daftar request masih "
            "kosong, biarkan Network terbuka lalu **reload halaman** atau buka "
            "kembali menu Pengajuan."
        )
        img = tutorial_dir / "03_network.png"
        if img.exists():
            st.image(
                str(img),
                caption="Pilih tab Network pada Chrome DevTools.",
                use_container_width=True,
            )

        st.markdown("### 5. Aktifkan filter Fetch/XHR")
        st.markdown(
            "Klik **Fetch/XHR** agar yang tampil terutama request data aplikasi. "
            "Pilih request yang menuju domain **simba.kemenag.go.id** dan berisi "
            "data daftar lembaga. Hindari request ke `google-analytics.com`."
        )
        img = tutorial_dir / "04_fetch_xhr.png"
        if img.exists():
            st.image(
                str(img),
                caption="Gunakan filter Fetch/XHR.",
                use_container_width=True,
            )

        st.markdown("### 6. Salin Request URL")
        st.markdown(
            "Klik request SIMBA yang benar, buka tab **Headers**, lalu pada bagian "
            "**General → Request URL** salin URL **secara lengkap**, termasuk query "
            "parameter jika ada. Tempel URL tersebut ke kolom **Request URL AJAX "
            "Lembaga** pada sidebar aplikasi."
        )
        img = tutorial_dir / "05_request_url.png"
        if img.exists():
            st.image(
                str(img),
                caption="Headers → General → Request URL. Salin URL lengkap.",
                use_container_width=True,
            )

        st.markdown("### 7. Salin Cookie Session")
        st.markdown(
            "Masih pada request SIMBA yang sama, buka tab **Cookies** atau cari "
            "**Request Headers → Cookie**. Salin **seluruh nilai Cookie** yang "
            "dikirim browser untuk request SIMBA, lalu tempel ke kolom **Cookie "
            "Session** pada sidebar aplikasi. Jangan hanya menyalin satu cookie "
            "jika browser mengirim beberapa pasangan cookie."
        )
        img = tutorial_dir / "06_cookie_redacted.png"
        if img.exists():
            st.image(
                str(img),
                caption=(
                    "Contoh lokasi Cookie. Nilai pada gambar sengaja disamarkan; "
                    "di browser Anda salin nilai asli secara privat."
                ),
                use_container_width=True,
            )

        st.markdown("### 8. Isi koneksi di sidebar dan Muat Data")
        st.markdown(
            "Setelah Request URL dan Cookie diperoleh, isi sidebar aplikasi: "
            "**Cookie Session**, **Request URL AJAX Lembaga**, dan **Method "
            "Lembaga** sesuai Method yang terlihat di Network (GET/POST). "
            "Kemudian klik **🔄 Muat Data**. Untuk pengujian pertama gunakan "
            "**DRY RUN**, setelah seluruh data terbaca benar barulah gunakan "
            "**LIVE SIMBA**."
        )

        st.info(
            "Jika data tidak muncul, ambil Request URL dan Cookie yang terbaru. "
            "Session SIMBA dapat kedaluwarsa setelah logout atau setelah beberapa waktu."
        )


def load_config():
    config_path = Path(
        "config.yaml"
    )

    if not config_path.exists():
        st.error(
            "config.yaml tidak ditemukan."
        )
        st.stop()

    with config_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(
            file
        )


def parse_extra_params(
    raw_text: str,
) -> dict:
    result = {}

    for line in raw_text.splitlines():
        line = line.strip()

        if (
            not line
            or "=" not in line
        ):
            continue

        key, value = (
            line.split(
                "=",
                1,
            )
        )

        key = key.strip()
        value = value.strip()

        if key:
            result[
                key
            ] = value

    return result


def render_pdf(
    pdf_bytes: bytes,
    height: int = 900,
):
    if not pdf_bytes:
        st.warning(
            "Data PDF kosong."
        )
        return

    try:
        pdf_viewer(
            input=pdf_bytes,
            height=height,
        )

    except Exception as exc:
        st.error(
            f"Gagal menampilkan PDF: {exc}"
        )




def render_document_reminder(
    *,
    aid_title: str,
    aid_id: str,
    document_name: str,
) -> None:
    reminders = get_document_reminders(
        aid_title=aid_title,
        aid_id=aid_id,
        document_name=document_name,
    )

    if not reminders:
        return

    items = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in reminders
    )

    st.markdown(
        (
            '<div class="doc-reminder">'
            '<strong>📌 Pengingat Verval</strong>'
            f'<ul>{items}</ul>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def resolve_aid_title(
    client: SimbaClient,
    institution,
) -> str:
    title = getattr(
        institution,
        "aid_title",
        "",
    )

    if title:
        return title

    try:
        title = (
            client.discover_aid_title(
                institution.detail_url
            )
        )

        if title:
            return title

    except Exception:
        pass

    aid_id = getattr(
        institution,
        "aid_category_id",
        "",
    )

    known_aids = {
        "130": (
            "Bantuan Halaqah Pesantren dan "
            "Pendidikan Keagamaan Islam "
            "Tahun Anggaran 2026"
        ),
    }

    if aid_id in known_aids:
        return known_aids[
            aid_id
        ]

    if aid_id:
        return (
            f"Program Bantuan "
            f"(ID {aid_id})"
        )

    return "Program Bantuan SIMBA"


def decision_display(
    code: str,
) -> str:
    return {
        "approve": "Verifikasi Proposal",
        "reject_institution": (
            "Tolak/Revisi → Kembalikan ke Lembaga"
        ),
        "reject_district": (
            "Tolak/Revisi → Kembalikan ke Kabupaten"
        ),
    }.get(
        code,
        code,
    )


def is_post_transition_state(
    submission_record: dict | None,
) -> bool:
    if not submission_record:
        return False

    return (
        submission_record.get(
            "state"
        )
        in {
            "SENT_UNCONFIRMED",
            "CONFIRMED",
        }
    )


def reset_verval_widget_state_after_submit():
    """
    Dijalankan pada rerun SETELAH submit berhasil, sebelum widget dibuat.

    Tujuannya:
    - proposal lama tidak tetap terbuka,
    - pencarian dikosongkan,
    - viewer dokumen direset,
    - pilihan dokumen/keputusan lama tidak ikut proposal berikutnya.
    """
    exact_keys = {
        "institution_selector",
        "institution_search",
    }

    prefixes = (
        "document_selector_",
        "pending_doc_key_",
        "revision_mode_",
        "decision_",
        "verification_note_",
        "verification_note_source_",
        "doc_flash_",
    )

    for key in list(
        st.session_state.keys()
    ):
        if (
            key in exact_keys
            or key.startswith(
                prefixes
            )
        ):
            st.session_state.pop(
                key,
                None,
            )

    st.session_state[
        "document_cache"
    ] = {}

    st.session_state[
        "pending_verification"
    ] = None

    st.session_state[
        "verification_preview"
    ] = None

    st.session_state[
        "verification_check"
    ] = None

    st.session_state[
        "live_submission_result"
    ] = None

    st.session_state[
        "live_verification_evidence"
    ] = None

    st.session_state[
        "verification_form_inspection"
    ] = {}


config = load_config()


default_states = {
    "institutions": [],
    "institution_meta": {},
    "document_cache": {},
    "pending_verification": None,
    "verification_preview": None,
    "verification_check": None,
    "live_submission_result": None,
    "live_verification_evidence": None,
    "verification_form_inspection": {},
    "reset_after_successful_submit": False,
    "next_institution_application_id": None,
    "post_submit_flash": None,
}

for key, value in (
    default_states.items()
):
    if key not in st.session_state:
        st.session_state[
            key
        ] = value


if st.session_state.get(
    "reset_after_successful_submit",
    False,
):
    reset_verval_widget_state_after_submit()

    st.session_state[
        "reset_after_successful_submit"
    ] = False


st.title(
    "📑 SIMBA Verval Assistant"
)

st.caption(
    "Asisten pemeriksaan proposal bantuan SIMBA — V8.1.4 Tutorial Penggunaan (Halaqah • Kemitraan • Prasarana)."
)


with st.sidebar:
    st.header(
        "Koneksi SIMBA"
    )

    if APP_PASSWORD:
        st.success(
            "🔐 Akses aplikasi dilindungi APP_PASSWORD."
        )
    else:
        st.warning(
            "Deployment publik: sangat disarankan mengatur APP_PASSWORD "
            "di Streamlit Secrets."
        )

    st.caption(
        "Cookie SIMBA jangan disimpan di GitHub/Streamlit Secrets. "
        "Tempel hanya saat sesi kerja dan logout dari SIMBA bila selesai."
    )

    cookie_header = st.text_area(
        "Cookie Session",
        height=110,
        key="cookie_session",
        placeholder=(
            "Tempel cookie session terbaru..."
        ),
    )

    st.caption(
        "Cookie hanya digunakan selama aplikasi berjalan."
    )

    st.divider()

    st.subheader(
        "Daftar Lembaga"
    )

    institution_ajax_url = (
        st.text_input(
            "Request URL AJAX Lembaga",
            key="institution_ajax_url",
        )
    )

    institution_method = (
        st.selectbox(
            "Method Lembaga",
            [
                "GET",
                "POST",
            ],
            key="institution_method",
        )
    )

    page_size = st.number_input(
        "Jumlah Data",
        min_value=10,
        max_value=1000,
        value=500,
        step=10,
        key="page_size",
    )

    institution_params_text = (
        st.text_area(
            "Parameter Tambahan Lembaga",
            height=90,
            key="institution_params",
        )
    )

    st.divider()

    st.subheader(
        "Review Proposal"
    )

    review_ajax_override = (
        st.text_input(
            "AJAX Dokumen",
            placeholder=(
                "Opsional. Kosongkan untuk auto-discovery."
            ),
            key="review_ajax_override",
        )
    )

    review_method = (
        st.selectbox(
            "Method Dokumen",
            [
                "GET",
                "POST",
            ],
            key="review_method",
        )
    )

    review_params_text = (
        st.text_area(
            "Parameter Tambahan Dokumen",
            height=90,
            key="review_params",
        )
    )

    st.divider()

    st.subheader("Mode Verifikasi")

    execution_mode = st.radio(
        "Mode Eksekusi",
        [
            "DRY RUN",
            "LIVE SIMBA",
        ],
        index=0,
        key="execution_mode",
        help=(
            "DRY RUN tidak mengubah SIMBA. LIVE SIMBA hanya "
            "diizinkan bila form Hasil Verifikasi dapat dibaca "
            "langsung dari HTML SIMBA."
        ),
    )

    if execution_mode == "DRY RUN":
        st.info(
            "DRY RUN: tidak ada POST perubahan status."
        )
    else:
        st.warning(
            "LIVE SIMBA: keputusan akan benar-benar dikirim "
            "ke SIMBA setelah konfirmasi Ya."
        )


render_usage_tutorial(
    expanded=not bool(cookie_header),
)


if not cookie_header:
    st.info(
        "Masukkan Cookie Session SIMBA di sidebar setelah mengikuti tutorial di atas."
    )
    st.stop()


# Pisahkan review/submission log berdasarkan session SIMBA tanpa
# menyimpan Cookie itu sendiri ke disk. Ini mencegah data review
# pengguna A tercampur dengan pengguna B pada Streamlit Cloud.
session_storage_key = hashlib.sha256(
    cookie_header.encode(
        "utf-8",
        errors="ignore",
    )
).hexdigest()[:20]

review_store = LocalReviewStore(
    f"data/verval_state_{session_storage_key}.json"
)

submission_log = SubmissionLog(
    f"data/submission_log_{session_storage_key}.json"
)


client = SimbaClient(
    base_url=config[
        "base_url"
    ],
    cookie_header=cookie_header,
)

live_engine = VerificationFormEngine(
    client=client,
    submission_log=submission_log,
)


tab_verval, tab_debug = st.tabs(
    [
        "✅ Verval",
        "🔧 Debug",
    ]
)


with tab_debug:
    st.subheader(
        "Debug AJAX Lembaga"
    )

    if st.button(
        "Tes AJAX Lembaga",
        key="debug_ajax_lembaga",
    ):
        try:
            institutions, meta = (
                client.list_institutions_ajax(
                    institution_ajax_url,
                    method=(
                        institution_method
                    ),
                    page_size=int(
                        page_size
                    ),
                    extra_params=(
                        parse_extra_params(
                            institution_params_text
                        )
                    ),
                )
            )

            st.success(
                f"{len(institutions)} lembaga terbaca."
            )

            st.json(
                meta
            )

        except Exception as exc:
            st.error(
                str(exc)
            )


with tab_verval:
    post_submit_flash = (
        st.session_state.pop(
            "post_submit_flash",
            None,
        )
    )

    if post_submit_flash:
        flash_status = (
            post_submit_flash.get(
                "status",
                ""
            )
        )
        flash_name = (
            post_submit_flash.get(
                "name",
                ""
            )
        )
        flash_destination = (
            post_submit_flash.get(
                "destination",
                ""
            )
        )

        message = (
            f"✅ {flash_name} selesai diproses. "
            f"Status SIMBA: {flash_status}."
        )

        if flash_destination:
            message += (
                f" Tujuan: {flash_destination}."
            )

        st.success(
            message
        )
        st.caption(
            "Daftar lembaga sudah dimuat ulang otomatis dan "
            "aplikasi melanjutkan ke proposal berikutnya."
        )

    head1, head2 = st.columns(
        [
            5,
            1,
        ]
    )

    with head1:
        st.subheader(
            "Daftar Lembaga"
        )

    with head2:
        load_clicked = st.button(
            "🔄 Muat Data",
            use_container_width=True,
            key="load_data",
        )

    if load_clicked:
        try:
            institutions, meta = (
                client.list_institutions_ajax(
                    institution_ajax_url,
                    method=(
                        institution_method
                    ),
                    page_size=int(
                        page_size
                    ),
                    extra_params=(
                        parse_extra_params(
                            institution_params_text
                        )
                    ),
                )
            )

            st.session_state[
                "institutions"
            ] = institutions

            st.session_state[
                "institution_meta"
            ] = meta

            st.session_state[
                "document_cache"
            ] = {}

            st.session_state[
                "pending_verification"
            ] = None

            st.session_state[
                "verification_preview"
            ] = None

            st.session_state[
                "verification_check"
            ] = None

            st.session_state[
                "live_submission_result"
            ] = None

            st.session_state[
                "live_verification_evidence"
            ] = None

            st.session_state[
                "verification_form_inspection"
            ] = {}

            st.success(
                f"{len(institutions)} lembaga berhasil dimuat."
            )

        except SimbaError as exc:
            st.error(
                str(exc)
            )

    institutions = (
        st.session_state[
            "institutions"
        ]
    )

    institution_meta = (
        st.session_state[
            "institution_meta"
        ]
    )

    if institution_meta:
        m1, m2, m3 = (
            st.columns(3)
        )

        m1.metric(
            "Total SIMBA",
            institution_meta.get(
                "recordsTotal",
                0,
            ),
        )

        m2.metric(
            "Filtered",
            institution_meta.get(
                "recordsFiltered",
                0,
            ),
        )

        m3.metric(
            "Termuat",
            institution_meta.get(
                "loaded",
                0,
            ),
        )

    if not institutions:
        st.info(
            "Klik Muat Data terlebih dahulu."
        )

    else:
        query = st.text_input(
            "Cari Pesantren / NSPP",
            key="institution_search",
        )

        filtered = institutions

        if query:
            q = query.lower()

            filtered = [
                item
                for item in institutions
                if (
                    q in item.name.lower()
                    or q in item.nspp.lower()
                )
            ]

        if not filtered:
            st.warning(
                "Lembaga tidak ditemukan."
            )

        else:
            options = {
                (
                    f"{item.name} | "
                    f"{item.nspp} | "
                    f"ID {item.application_id}"
                ): item
                for item in filtered
            }

            next_application_id = (
                st.session_state.get(
                    "next_institution_application_id"
                )
            )

            if next_application_id:
                next_label = next(
                    (
                        label
                        for label, item
                        in options.items()
                        if item.application_id
                        == next_application_id
                    ),
                    None,
                )

                if next_label:
                    st.session_state[
                        "institution_selector"
                    ] = next_label

                st.session_state[
                    "next_institution_application_id"
                ] = None

            # Jika value lama sudah tidak ada karena proposal selesai
            # diproses dan keluar dari antrean, hapus value lama.
            current_selector_value = (
                st.session_state.get(
                    "institution_selector"
                )
            )

            if (
                current_selector_value
                and current_selector_value
                not in options
            ):
                st.session_state.pop(
                    "institution_selector",
                    None,
                )

            selected_label = (
                st.selectbox(
                    "Pilih lembaga",
                    list(
                        options.keys()
                    ),
                    key="institution_selector",
                )
            )

            institution = (
                options[
                    selected_label
                ]
            )

            if not institution.detail_url:
                st.error(
                    "URL Detail lembaga tidak ditemukan."
                )
                st.stop()

            aid_title = resolve_aid_title(
                client,
                institution,
            )

            aid_id = getattr(
                institution,
                "aid_category_id",
                "",
            )

            with st.container(
                border=True
            ):
                st.caption(
                    "PROGRAM BANTUAN"
                )

                st.markdown(
                    f"### {aid_title}"
                )

                if aid_id:
                    st.caption(
                        f"ID Bantuan: {aid_id}"
                    )

            # =================================================
            # RESOLVE DETAIL URL
            # =================================================
            # Setelah POST sukses, route lama
            # /diverifikasikabupaten/... dapat menjadi 404 karena
            # proposal berpindah ke /diproseskanwil/....
            #
            # Karena itu jangan langsung menganggap 404 sebagai gagal.
            # Coba route hasil Kanwil dengan GET-only.
            current_submission_record = (
                submission_log.get(
                    institution.application_id
                )
            )

            prefer_processed_route = (
                is_post_transition_state(
                    current_submission_record
                )
            )

            try:
                discovered = (
                    client.discover_institution_links_resilient(
                        institution.detail_url,
                        prefer_processed=(
                            prefer_processed_route
                        ),
                    )
                )

                active_detail_url = (
                    discovered.get(
                        "detail_url"
                    )
                    or institution.detail_url
                )

                # Update object hanya di memory agar seluruh GET berikutnya
                # memakai route yang masih aktif.
                institution.detail_url = (
                    active_detail_url
                )

            except SimbaError as exc:
                if prefer_processed_route:
                    st.warning(
                        "Proposal kemungkinan sudah berpindah status di SIMBA, "
                        "tetapi halaman detail aktif belum dapat dibaca. "
                        "Jangan kirim ulang proposal ini."
                    )

                    st.caption(
                        str(exc)
                    )

                    # Jangan crash setelah POST. Tampilkan hasil yang sudah
                    # tercatat dan hentikan pemuatan detail lama.
                    discovered = {
                        "detail_url": "",
                        "proposal_review_url": "",
                        "verification_url": "",
                    }
                    active_detail_url = ""
                else:
                    st.error(
                        str(exc)
                    )
                    st.stop()

            review_url = (
                discovered.get(
                    "proposal_review_url"
                )
                or ""
            )

            verification_url = (
                discovered.get(
                    "verification_url"
                )
                or ""
            )

            try:
                profile = (
                    client.parse_profile(
                        active_detail_url
                    )
                    if active_detail_url
                    else {}
                )
            except Exception:
                profile = {}

            completeness = {
                "completed": None,
                "total": None,
                "text": "",
            }

            if review_url:
                try:
                    completeness = (
                        client.get_proposal_completeness(
                            review_url
                        )
                    )
                except Exception:
                    pass

            documents = []
            document_meta = {}

            if review_url:
                try:
                    (
                        documents,
                        document_meta,
                    ) = (
                        client.list_proposal_documents_auto(
                            review_url,
                            explicit_ajax_url=(
                                review_ajax_override
                            ),
                            method=(
                                review_method
                            ),
                            page_size=500,
                            extra_params=(
                                parse_extra_params(
                                    review_params_text
                                )
                            ),
                        )
                    )

                except SimbaError as exc:
                    st.warning(
                        f"Gagal membaca dokumen proposal: {exc}"
                    )

            recommendation_url = getattr(
                institution,
                "recommendation_url",
                "",
            )

            if recommendation_url:
                already_exists = any(
                    doc.name.lower()
                    == "surat rekomendasi kabupaten"
                    for doc in documents
                )

                if not already_exists:
                    documents.append(
                        ProposalDocument(
                            id="recommendation-district",
                            proposal_id=(
                                institution.application_id
                            ),
                            category_id="recommendation-district",
                            number=str(
                                len(documents) + 1
                            ),
                            stage="Kabupaten",
                            name="Surat Rekomendasi Kabupaten",
                            file_name=getattr(
                                institution,
                                "recommendation_path",
                                "",
                            ),
                            file_url=(
                                recommendation_url
                            ),
                            file_type="pdf",
                            size="",
                            date="",
                            score="",
                            is_document_valid=None,
                            text_value="",
                        )
                    )

            # =================================================
            # LOCAL CHECKLIST STATE (PERSISTEN PER PENGAJUAN)
            # =================================================

            review_state = review_store.ensure_documents(
                institution.application_id,
                documents,
            )

            review_summary = summarize_reviews(
                review_state,
                documents,
            )

            left, right = st.columns(
                [
                    1,
                    2.6,
                ],
                gap="large",
            )

            with left:
                st.subheader(
                    "Profil Lembaga"
                )

                with st.container(
                    border=True
                ):
                    st.markdown(
                        f"### {institution.name or '-'}"
                    )

                    st.caption(
                        "NSPP"
                    )
                    st.markdown(
                        f"**{institution.nspp or '-'}**"
                    )

                    st.caption(
                        "ID Pengajuan"
                    )
                    st.markdown(
                        f"**{institution.application_id or '-'}**"
                    )

                    st.caption(
                        "Status"
                    )

                    display_status = (
                        institution.status
                        or "-"
                    )

                    evidence_now = (
                        st.session_state.get(
                            "live_verification_evidence"
                        )
                    )

                    if (
                        evidence_now
                        and st.session_state.get(
                            "pending_verification",
                            {},
                        ).get(
                            "application_id"
                        )
                        == institution.application_id
                        and evidence_now.get(
                            "confirmed"
                        )
                    ):
                        display_status = (
                            evidence_now.get(
                                "expected_status"
                            )
                            or display_status
                        )

                    st.markdown(
                        f"**{display_status}**"
                    )

                st.markdown(
                    "#### Alamat"
                )
                st.write(
                    institution.address
                    or "-"
                )

                st.markdown(
                    "#### Tanggal Pengajuan"
                )
                st.write(
                    institution.submission_date
                    or "-"
                )

                st.markdown(
                    "#### Catatan Kabupaten"
                )

                if (
                    institution.district_note
                    or ""
                ).strip() in {
                    "",
                    "-",
                    "•",
                }:
                    st.write("-")
                else:
                    st.write(
                        institution.district_note
                    )

                if profile:
                    with st.expander(
                        "Profil Lengkap"
                    ):
                        for (
                            key,
                            value,
                        ) in profile.items():
                            st.markdown(
                                f"**{key}**"
                            )
                            st.write(
                                value
                            )

            with right:
                st.subheader(
                    "Dokumen Proposal Lembaga"
                )

                if (
                    completeness.get(
                        "completed"
                    )
                    is not None
                ):
                    completed = (
                        completeness[
                            "completed"
                        ]
                    )
                    total = (
                        completeness[
                            "total"
                        ]
                    )

                    if completed == total:
                        st.success(
                            "Kelengkapan Persyaratan: "
                            f"{completed} dari {total}"
                        )
                    else:
                        st.warning(
                            "Kelengkapan Persyaratan: "
                            f"{completed} dari {total}"
                        )

                if not documents:
                    st.error(
                        "Dokumen belum berhasil dibaca."
                    )

                    with st.expander(
                        "Debug Dokumen"
                    ):
                        st.json(
                            document_meta
                        )

                else:
                    pdf_count = sum(
                        1
                        for doc in documents
                        if doc.file_type == "pdf"
                    )

                    text_count = sum(
                        1
                        for doc in documents
                        if doc.file_type == "text"
                    )

                    d1, d2, d3 = (
                        st.columns(3)
                    )

                    d1.metric(
                        "Total Dokumen",
                        len(documents),
                    )

                    d2.metric(
                        "PDF",
                        pdf_count,
                    )

                    d3.metric(
                        "TEXT",
                        text_count,
                    )

                    def document_option_label(i):
                        item = documents[i]
                        item_key = make_document_key(
                            item
                        )
                        item_status = (
                            review_state
                            .get("documents", {})
                            .get(item_key, {})
                            .get(
                                "status",
                                STATUS_NOT_REVIEWED,
                            )
                        )

                        icon = {
                            STATUS_NOT_REVIEWED: "⬜",
                            STATUS_OK: "✅",
                            STATUS_REVISION: "⚠️",
                        }.get(
                            item_status,
                            "⬜",
                        )

                        return (
                            f"{icon} {item.number}. {item.name}"
                        )

                    # Gunakan document_key sebagai nilai selectbox, bukan index.
                    # Ini membuat navigasi stabil walau label/status berubah saat rerun.
                    document_keys = [
                        make_document_key(item)
                        for item in documents
                    ]
                    document_by_key = {
                        make_document_key(item): item
                        for item in documents
                    }
                    document_index_by_key = {
                        key: idx
                        for idx, key in enumerate(document_keys)
                    }

                    selector_key = (
                        "document_selector_"
                        + institution.application_id
                    )

                    pending_key = (
                        "pending_doc_key_"
                        + institution.application_id
                    )

                    # Semua perpindahan dokumen melewati satu jalur:
                    # pending_doc_key -> selectbox. Tidak ada campuran antara
                    # ubah widget langsung dan pending index.
                    if pending_key in st.session_state:
                        target_key = st.session_state.pop(
                            pending_key
                        )
                        if target_key in document_by_key:
                            st.session_state[
                                selector_key
                            ] = target_key

                    if (
                        selector_key not in st.session_state
                        or st.session_state[
                            selector_key
                        ] not in document_by_key
                    ):
                        st.session_state[
                            selector_key
                        ] = document_keys[0]

                    def document_key_label(key):
                        idx = document_index_by_key[key]
                        return document_option_label(idx)

                    selected_document_key = (
                        st.selectbox(
                            "Pilih dokumen",
                            document_keys,
                            format_func=document_key_label,
                            key=selector_key,
                        )
                    )

                    selected_index = (
                        document_index_by_key[
                            selected_document_key
                        ]
                    )

                    doc = (
                        document_by_key[
                            selected_document_key
                        ]
                    )

                    st.markdown(
                        f"## {doc.name}"
                    )

                    render_document_reminder(
                        aid_title=aid_title,
                        aid_id=aid_id,
                        document_name=doc.name,
                    )

                    i1, i2, i3 = (
                        st.columns(3)
                    )

                    i1.write(
                        "**Tahap**"
                    )
                    i1.write(
                        doc.stage
                        or "-"
                    )

                    i2.write(
                        "**Tipe**"
                    )
                    i2.write(
                        (
                            doc.file_type.upper()
                            if doc.file_type
                            else "-"
                        )
                    )

                    i3.write(
                        "**Tanggal**"
                    )
                    i3.write(
                        doc.date
                        or "-"
                    )

                    st.divider()

                    if doc.file_type == "text":
                        st.info(
                            "Dokumen ini berupa teks, bukan PDF."
                        )

                        if doc.text_value:
                            safe_text = html.escape(
                                doc.text_value
                            )

                            st.markdown(
                                "### Isi"
                            )

                            st.markdown(
                                f"""<div class="text-document">{safe_text}</div>""",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.warning(
                                "Isi teks tidak tersedia."
                            )

                    elif doc.file_type == "pdf":
                        if not doc.file_url:
                            st.error(
                                "URL PDF tidak ditemukan."
                            )
                        else:
                            cache_key = (
                                doc.file_url
                            )

                            cached = (
                                st.session_state[
                                    "document_cache"
                                ].get(
                                    cache_key
                                )
                            )

                            if not cached:
                                try:
                                    with st.spinner(
                                        "Memuat PDF..."
                                    ):
                                        cached = (
                                            client.fetch_document(
                                                doc.file_url
                                            )
                                        )

                                        st.session_state[
                                            "document_cache"
                                        ][
                                            cache_key
                                        ] = cached

                                except SimbaError as exc:
                                    st.error(
                                        str(exc)
                                    )

                            if cached:
                                (
                                    file_bytes,
                                    content_type,
                                    final_url,
                                ) = cached

                                is_pdf = (
                                    "pdf"
                                    in content_type
                                    or file_bytes[:4]
                                    == b"%PDF"
                                )

                                if is_pdf:
                                    render_pdf(
                                        file_bytes,
                                        height=900,
                                    )
                                elif (
                                    "image"
                                    in content_type
                                ):
                                    st.image(
                                        file_bytes,
                                        use_container_width=True,
                                    )
                                else:
                                    st.warning(
                                        "File bukan PDF/image."
                                    )

            # =================================================
            # PEMERIKSAAN DOKUMEN — CEPAT / ONE-CLICK
            # =================================================

            if documents:
                st.divider()
                st.subheader("Pemeriksaan Dokumen")
                st.caption(
                    "Klik **Sesuai** bila dokumen benar. Hasil langsung tersimpan dan "
                    "berpindah tepat **1 dokumen** ke berikutnya. Klik **Perbaikan / Tidak Sesuai** "
                    "hanya bila ada masalah."
                )

                selected_doc = documents[selected_index]
                document_key = make_document_key(selected_doc)
                checklist_title, checklist_rules = get_rules_for_document(
                    selected_doc.name,
                    aid_title=aid_title,
                    aid_id=aid_id,
                )
                current_review = (
                    review_state.get("documents", {}).get(document_key, {})
                )
                saved_status = current_review.get("status", STATUS_NOT_REVIEWED)

                selector_key = "document_selector_" + institution.application_id
                pending_key = "pending_doc_key_" + institution.application_id
                revision_mode_key = (
                    "revision_mode_" + institution.application_id + "_" + document_key
                )

                # Dokumen yang sebelumnya sudah berstatus Perlu Perbaikan langsung
                # membuka panel temuan. Dokumen baru / Sesuai tetap ringkas.
                if revision_mode_key not in st.session_state:
                    st.session_state[revision_mode_key] = (
                        saved_status == STATUS_REVISION
                    )

                def _next_document_key():
                    current_key = make_document_key(
                        selected_doc
                    )
                    current_pos = document_index_by_key.get(
                        current_key,
                        selected_index,
                    )

                    if current_pos < len(document_keys) - 1:
                        return document_keys[
                            current_pos + 1
                        ]

                    return current_key

                def _mark_ok_and_next():
                    review_store.save_document_review(
                        institution.application_id,
                        selected_doc,
                        status=STATUS_OK,
                        issues=[],
                        note="",
                    )
                    st.session_state[revision_mode_key] = False

                    # Jangan ubah value selectbox langsung dari callback.
                    # Cukup set target berikutnya; pada rerun berikutnya
                    # target diterapkan sebelum widget dibuat.
                    st.session_state[
                        pending_key
                    ] = _next_document_key()

                    st.session_state[
                        "doc_flash_" + institution.application_id
                    ] = f"✅ {selected_doc.name}: Sesuai"

                def _open_revision():
                    st.session_state[revision_mode_key] = True

                def _go_next_only():
                    st.session_state[
                        pending_key
                    ] = _next_document_key()

                flash_key = "doc_flash_" + institution.application_id
                flash_message = st.session_state.pop(flash_key, None)
                if flash_message:
                    st.success(flash_message)

                if saved_status == STATUS_OK:
                    st.success("Status tersimpan: ✅ Sesuai")
                elif saved_status == STATUS_REVISION:
                    st.warning("Status tersimpan: ⚠️ Perlu Perbaikan / Tidak Sesuai")

                choice_ok, choice_revision = st.columns(2)

                with choice_ok:
                    st.button(
                        "✅ Sesuai",
                        type="primary",
                        use_container_width=True,
                        key="quick_ok_" + institution.application_id + "_" + document_key,
                        on_click=_mark_ok_and_next,
                    )

                with choice_revision:
                    st.button(
                        "⚠️ Perbaikan / Tidak Sesuai",
                        use_container_width=True,
                        key="quick_revision_" + institution.application_id + "_" + document_key,
                        on_click=_open_revision,
                    )

                selected_issues = []
                note = ""

                if st.session_state.get(revision_mode_key, False):
                    st.warning(
                        "Centang hanya masalah yang ditemukan. Temuan akan dirangkum "
                        "otomatis menjadi catatan perbaikan."
                    )
                    st.markdown(f"**Temuan pada {checklist_title}:**")

                    old_issues = set(current_review.get("issues") or [])
                    for i, rule in enumerate(checklist_rules):
                        issue_key = (
                            "issue_" + institution.application_id + "_" + document_key + "_" + str(i)
                        )
                        if issue_key not in st.session_state:
                            st.session_state[issue_key] = rule in old_issues
                        if st.checkbox(rule, key=issue_key):
                            selected_issues.append(rule)

                    note_key = (
                        "doc_note_" + institution.application_id + "_" + document_key
                    )
                    if note_key not in st.session_state:
                        st.session_state[note_key] = current_review.get("note", "")

                    note = st.text_area(
                        "Catatan tambahan (opsional)",
                        key=note_key,
                        height=90,
                        placeholder="Tambahkan keterangan singkat bila diperlukan...",
                    )

                    save_revision_col, cancel_revision_col = st.columns([2, 1])

                    with save_revision_col:
                        if st.button(
                            "💾 Simpan Perbaikan & Dokumen Selanjutnya",
                            type="primary",
                            use_container_width=True,
                            key=(
                                "save_revision_next_"
                                + institution.application_id
                                + "_"
                                + document_key
                            ),
                        ):
                            if not selected_issues and not note.strip():
                                st.error(
                                    "Centang minimal satu temuan atau isi catatan tambahan."
                                )
                            else:
                                review_store.save_document_review(
                                    institution.application_id,
                                    selected_doc,
                                    status=STATUS_REVISION,
                                    issues=selected_issues,
                                    note=note,
                                )
                                st.session_state[revision_mode_key] = False
                                # Perubahan widget dilakukan lewat callback-style rerun state.
                                # Karena tombol diproses setelah selectbox dibuat, gunakan state
                                # navigator lalu sinkronkan pada rerun berikutnya.
                                st.session_state[
                                    pending_key
                                ] = _next_document_key()
                                st.session_state[
                                    "doc_flash_" + institution.application_id
                                ] = f"⚠️ {selected_doc.name}: Perlu Perbaikan"
                                st.rerun()

                    with cancel_revision_col:
                        if st.button(
                            "Batal",
                            use_container_width=True,
                            key=(
                                "cancel_revision_"
                                + institution.application_id
                                + "_"
                                + document_key
                            ),
                        ):
                            st.session_state[revision_mode_key] = False
                            st.rerun()

                # Tombol navigasi selalu tersedia untuk berpindah tanpa mengubah hasil.
                st.button(
                    "⏭️ Dokumen Selanjutnya (tanpa mengubah status)",
                    use_container_width=True,
                    key="next_doc_" + institution.application_id + "_" + document_key,
                    on_click=_go_next_only,
                )

            # Refresh summary setelah kemungkinan perubahan state.
            review_state = review_store.ensure_documents(
                institution.application_id,
                documents,
            )
            review_summary = summarize_reviews(
                review_state,
                documents,
            )

            # =================================================
            # RINGKASAN SINGKAT
            # =================================================

            if documents:
                st.divider()
                st.subheader("Ringkasan Pemeriksaan")
                r1, r2, r3 = st.columns(3)
                r1.metric("Diperiksa", f"{review_summary['reviewed']}/{review_summary['total']}")
                r2.metric("Sesuai", review_summary["counts"][STATUS_OK])
                r3.metric("Perlu Perbaikan", review_summary["counts"][STATUS_REVISION])

                if review_summary["issues"]:
                    with st.expander("Lihat dokumen yang perlu diperbaiki", expanded=False):
                        for issue in review_summary["issues"]:
                            st.markdown(f"**{issue['document_name']}**")
                            for item in issue.get("issues", []):
                                st.write("•", item)
                            if issue.get("note"):
                                st.write("Catatan:", issue["note"])

            # =================================================
            # HASIL VERIFIKASI
            # =================================================

            st.divider()
            st.subheader("Hasil Verifikasi")

            decision_label = st.radio(
                "Pilih hasil verifikasi",
                [
                    "Verifikasi Proposal",
                    "Tolak Proposal (Revisi), dan Kembalikan ke Lembaga",
                    "Tolak Proposal (Revisi), dan Kembalikan ke Kabupaten",
                ],
                key="decision_" + institution.application_id,
            )

            decision_map = {
                "Verifikasi Proposal": "approve",
                "Tolak Proposal (Revisi), dan Kembalikan ke Lembaga": "reject_institution",
                "Tolak Proposal (Revisi), dan Kembalikan ke Kabupaten": "reject_district",
            }

            decision_code = decision_map[
                decision_label
            ]
            is_reject = (
                decision_code
                != "approve"
            )

            verification_note = ""
            auto_note = build_revision_note(
                review_summary
            )

            if is_reject:
                if (
                    decision_code
                    == "reject_institution"
                ):
                    st.info(
                        "Proposal akan dikembalikan ke Lembaga untuk diperbaiki."
                    )
                else:
                    st.info(
                        "Proposal akan dikembalikan ke Kabupaten untuk diperbaiki."
                    )

                note_key = (
                    "verification_note_"
                    + institution.application_id
                )
                source_key = (
                    "verification_note_source_"
                    + institution.application_id
                )
                desired_source = auto_note

                if (
                    source_key
                    not in st.session_state
                    or st.session_state[
                        source_key
                    ]
                    != desired_source
                ):
                    if auto_note:
                        st.session_state[
                            note_key
                        ] = auto_note

                    st.session_state[
                        source_key
                    ] = desired_source

                verification_note = (
                    st.text_area(
                        "Catatan Perbaikan",
                        key=note_key,
                        height=150,
                        placeholder=(
                            "Tuliskan bagian yang harus diperbaiki..."
                        ),
                    )
                )

                st.caption(
                    "Catatan hanya muncul ketika proposal ditolak/dikembalikan."
                )

            with st.container(
                border=True
            ):
                t1, t2 = st.columns(
                    2
                )

                with t1:
                    st.caption(
                        "Nama Lembaga"
                    )
                    st.write(
                        institution.name
                    )
                    st.caption(
                        "NSPP"
                    )
                    st.write(
                        institution.nspp
                    )

                with t2:
                    st.caption(
                        "ID Pengajuan"
                    )
                    st.write(
                        institution.application_id
                    )
                    st.caption(
                        "Program Bantuan"
                    )
                    st.write(
                        aid_title
                    )

            execution_mode = (
                st.session_state.get(
                    "execution_mode",
                    "DRY RUN",
                )
            )

            # ================================================
            # INSPEKSI FORM LIVE
            # ================================================

            form_inspection = {}

            if (
                execution_mode == "LIVE SIMBA"
                and not is_post_transition_state(
                    previous_submission
                    if "previous_submission" in locals()
                    else submission_log.get(
                        institution.application_id
                    )
                )
            ):
                if not verification_url:
                    st.error(
                        "URL Hasil Verifikasi tidak ditemukan. "
                        "LIVE diblokir."
                    )
                else:
                    try:
                        form_inspection = (
                            live_engine.inspect_verification_page(
                                verification_url
                            )
                        )

                        st.session_state[
                            "verification_form_inspection"
                        ] = form_inspection

                        decision_form = (
                            form_inspection.get(
                                "decisions",
                                {},
                            ).get(
                                decision_code,
                                {},
                            )
                        )

                        if decision_form.get(
                            "ready"
                        ):
                            if (
                                decision_code
                                == "reject_district"
                            ):
                                if (
                                    decision_form.get(
                                        "decision_source"
                                    )
                                    == "verified_network_capture"
                                ):
                                    st.success(
                                        "✅ LIVE Tolak → Kabupaten aktif. "
                                        "Request Network asli sudah diverifikasi: "
                                        "field terima_tolak dengan nilai "
                                        "tolak_kabupaten, menggunakan action POST "
                                        "form SIMBA yang sama dan catatan_wilayah."
                                    )
                                else:
                                    st.success(
                                        "✅ LIVE Tolak → Kabupaten aktif. "
                                        "Kontrol/form asli SIMBA berhasil ditemukan "
                                        "dan dibedakan dari jalur Lembaga."
                                    )
                            elif is_reject:
                                st.success(
                                    "Tujuan penolakan berhasil dibedakan dari form SIMBA."
                                )
                            else:
                                st.success(
                                    "Form SIMBA untuk keputusan ini berhasil dikenali."
                                )

                            with st.expander(
                                "Lihat struktur request yang terdeteksi",
                                expanded=False,
                            ):
                                st.write(
                                    "**Method:**",
                                    decision_form.get(
                                        "method"
                                    ),
                                )
                                st.write(
                                    "**Action URL:**",
                                    decision_form.get(
                                        "action_url"
                                    ),
                                )
                                st.write(
                                    "**Tipe form:**",
                                    decision_form.get(
                                        "enctype"
                                    ),
                                )
                                st.write(
                                    "**Field keputusan:**",
                                    decision_form.get(
                                        "decision_field"
                                    ),
                                )
                                st.write(
                                    "**Nilai keputusan:**",
                                    decision_form.get(
                                        "decision_value"
                                    ),
                                )
                                st.write(
                                    "**Sumber pemetaan keputusan:**",
                                    decision_form.get(
                                        "decision_source",
                                        "html_form",
                                    ),
                                )

                                st.write(
                                    "**Label asli SIMBA:**",
                                    decision_form.get(
                                        "decision_label"
                                    ),
                                )

                                if is_reject:
                                    st.write(
                                        "**Tujuan yang dipilih:**",
                                        (
                                            "LEMBAGA"
                                            if decision_code
                                            == "reject_institution"
                                            else "KABUPATEN"
                                        ),
                                    )
                                    st.write(
                                        "**Field catatan:**",
                                        decision_form.get(
                                            "note_field"
                                        ),
                                    )

                                file_fields = (
                                    decision_form.get(
                                        "file_field_names",
                                        [],
                                    )
                                )

                                if file_fields:
                                    st.write(
                                        "**Field file multipart (dikirim kosong):**"
                                    )
                                    for field in file_fields:
                                        st.write(
                                            "•",
                                            field,
                                        )

                                hidden_fields = (
                                    decision_form.get(
                                        "hidden_field_names",
                                        [],
                                    )
                                )

                                if hidden_fields:
                                    st.write(
                                        "**Hidden field:**"
                                    )

                                    for field in hidden_fields:
                                        st.write(
                                            "•",
                                            field,
                                        )

                                st.caption(
                                    "Nilai token/CSRF tidak ditampilkan."
                                )

                        else:
                            if (
                                decision_code
                                == "reject_district"
                            ):
                                st.warning(
                                    "⚠️ Hasil Tolak → Kabupaten sudah berhasil "
                                    "dipetakan dari SIMBA (status 'Ditolak kanwil "
                                    "ke kabupaten' dan catatan 'Catatan kanwil ke "
                                    "kabupaten'). Namun request POST asli Kabupaten "
                                    "belum ditemukan pada form proposal ini, sehingga "
                                    "aplikasi tidak akan menebak payload pengiriman."
                                )
                            else:
                                st.error(
                                    "Struktur POST untuk keputusan ini belum dapat "
                                    "dikenali dengan aman. LIVE diblokir."
                                )

                            if decision_form.get(
                                "error"
                            ):
                                st.caption(
                                    decision_form[
                                        "error"
                                    ]
                                )

                            diagnostic_controls = (
                                form_inspection.get(
                                    "diagnostic_controls",
                                    []
                                )
                            )

                            if diagnostic_controls:
                                with st.expander(
                                    "Diagnostik kontrol form SIMBA",
                                    expanded=False,
                                ):
                                    st.caption(
                                        "Token/CSRF/cookie tidak disertakan."
                                    )
                                    st.json(
                                        diagnostic_controls
                                    )

                    except Exception as exc:
                        st.error(
                            "Gagal membaca form Hasil Verifikasi: "
                            f"{exc}"
                        )

            # ================================================
            # GUARD POST GANDA
            # ================================================

            previous_submission = (
                submission_log.get(
                    institution.application_id
                )
            )

            if previous_submission:
                previous_state = (
                    previous_submission.get(
                        "state",
                        ""
                    )
                )

                if previous_state == "CONFIRMED":
                    st.success(
                        "Pengajuan ini tercatat sudah berhasil dikirim "
                        "dari aplikasi dan statusnya terkonfirmasi."
                    )

                elif previous_state == "SENT_UNCONFIRMED":
                    st.warning(
                        "Pengajuan ini sudah pernah di-POST tetapi hasilnya "
                        "belum terkonfirmasi. POST ulang otomatis diblokir."
                    )

                    if st.button(
                        "Saya sudah cek SIMBA — izinkan kirim ulang",
                        key=(
                            "clear_submission_guard_"
                            + institution.application_id
                        ),
                    ):
                        submission_log.clear(
                            institution.application_id
                        )
                        st.session_state[
                            "live_submission_result"
                        ] = None
                        st.session_state[
                            "live_verification_evidence"
                        ] = None
                        st.rerun()

            @st.dialog(
                "Konfirmasi Verifikasi"
            )
            def confirm_verification_dialog(
                preview: dict,
            ):
                if preview[
                    "decision"
                ] == "approve":
                    st.write(
                        "Apakah Anda yakin ingin menerima proposal "
                        "dan mengajukan proposal ke Admin Pusat?"
                    )
                elif preview[
                    "decision"
                ] == "reject_institution":
                    st.error(
                        "TUJUAN PENGEMBALIAN: LEMBAGA"
                    )
                    st.write(
                        "Apakah Anda yakin ingin mengembalikan proposal "
                        "ke Lembaga untuk diperbaiki?"
                    )
                else:
                    st.error(
                        "TUJUAN PENGEMBALIAN: KABUPATEN"
                    )
                    st.write(
                        "Apakah Anda yakin ingin mengembalikan proposal "
                        "ke Kabupaten untuk diperbaiki?"
                    )

                st.write(
                    f"**{preview['institution_name']}**"
                )
                st.caption(
                    f"NSPP {preview['nspp']} • "
                    f"ID Pengajuan {preview['application_id']}"
                )

                st.write(
                    "**Keputusan:**",
                    decision_display(
                        preview[
                            "decision"
                        ]
                    ),
                )

                if preview.get(
                    "note"
                ):
                    st.write(
                        "**Catatan Perbaikan:**"
                    )
                    st.write(
                        preview[
                            "note"
                        ]
                    )

                mode = (
                    preview.get(
                        "execution_mode",
                        "DRY RUN",
                    )
                )

                if mode == "DRY RUN":
                    st.info(
                        "DRY RUN — tidak ada POST ke SIMBA."
                    )
                else:
                    st.warning(
                        "LIVE SIMBA — klik Ya akan melakukan satu POST nyata."
                    )

                yes_col, no_col = (
                    st.columns(2)
                )

                with yes_col:
                    if st.button(
                        "Ya",
                        type="primary",
                        use_container_width=True,
                        key=(
                            "confirm_yes_"
                            + preview[
                                "application_id"
                            ]
                        ),
                    ):
                        try:
                            if mode == "DRY RUN":
                                check = (
                                    client.confirm_dry_run_result(
                                        institution=institution,
                                        before_snapshot=preview[
                                            "before_snapshot"
                                        ],
                                    )
                                )

                                st.session_state[
                                    "pending_verification"
                                ] = preview

                                st.session_state[
                                    "verification_preview"
                                ] = preview

                                st.session_state[
                                    "verification_check"
                                ] = check

                            else:
                                submit_result = (
                                    live_engine.submit_once(
                                        verification_url=(
                                            preview[
                                                "verification_url"
                                            ]
                                        ),
                                        institution=(
                                            institution
                                        ),
                                        decision=(
                                            preview[
                                                "decision"
                                            ]
                                        ),
                                        note=(
                                            preview.get(
                                                "note",
                                                "",
                                            )
                                        ),
                                    )
                                )

                                evidence = (
                                    live_engine.verify_after_submit(
                                        institution=(
                                            institution
                                        ),
                                        decision=(
                                            preview[
                                                "decision"
                                            ]
                                        ),
                                        submit_result=(
                                            submit_result
                                        ),
                                        institution_ajax_url=(
                                            institution_ajax_url
                                        ),
                                        institution_method=(
                                            institution_method
                                        ),
                                        institution_page_size=int(
                                            page_size
                                        ),
                                        institution_extra_params=(
                                            parse_extra_params(
                                                institution_params_text
                                            )
                                        ),
                                        expected_note=(
                                            preview.get(
                                                "note",
                                                "",
                                            )
                                        ),
                                    )
                                )

                                st.session_state[
                                    "pending_verification"
                                ] = preview

                                st.session_state[
                                    "live_submission_result"
                                ] = submit_result

                                st.session_state[
                                    "live_verification_evidence"
                                ] = evidence

                                # Jika status akhir sudah benar-benar berubah
                                # di server SIMBA, proposal tidak perlu tetap
                                # berada di layar. Muat ulang antrean secara
                                # otomatis dan pindah ke proposal berikutnya.
                                if evidence.get(
                                    "status_confirmed",
                                    False,
                                ):
                                    try:
                                        current_index = next(
                                            (
                                                idx
                                                for idx, item
                                                in enumerate(
                                                    institutions
                                                )
                                                if item.application_id
                                                == institution.application_id
                                            ),
                                            0,
                                        )

                                        refreshed_institutions, refreshed_meta = (
                                            client.list_institutions_ajax(
                                                institution_ajax_url,
                                                method=(
                                                    institution_method
                                                ),
                                                page_size=int(
                                                    page_size
                                                ),
                                                extra_params=(
                                                    parse_extra_params(
                                                        institution_params_text
                                                    )
                                                ),
                                            )
                                        )

                                        # Walaupun endpoint antrean sesaat masih
                                        # cache/stale, proposal yang statusnya sudah
                                        # terkonfirmasi jangan ditampilkan lagi.
                                        refreshed_institutions = [
                                            item
                                            for item
                                            in refreshed_institutions
                                            if item.application_id
                                            != institution.application_id
                                        ]

                                        refreshed_meta[
                                            "loaded"
                                        ] = len(
                                            refreshed_institutions
                                        )

                                        st.session_state[
                                            "institutions"
                                        ] = refreshed_institutions

                                        st.session_state[
                                            "institution_meta"
                                        ] = refreshed_meta

                                        next_id = None

                                        if refreshed_institutions:
                                            next_index = min(
                                                current_index,
                                                len(
                                                    refreshed_institutions
                                                ) - 1,
                                            )

                                            next_id = (
                                                refreshed_institutions[
                                                    next_index
                                                ].application_id
                                            )

                                        st.session_state[
                                            "next_institution_application_id"
                                        ] = next_id

                                        destination = ""

                                        if preview[
                                            "decision"
                                        ] == "reject_institution":
                                            destination = "Lembaga"
                                        elif preview[
                                            "decision"
                                        ] == "reject_district":
                                            destination = "Kabupaten"

                                        st.session_state[
                                            "post_submit_flash"
                                        ] = {
                                            "name": institution.name,
                                            "application_id": (
                                                institution.application_id
                                            ),
                                            "status": (
                                                evidence.get(
                                                    "queue_status",
                                                    ""
                                                )
                                                or evidence.get(
                                                    "expected_status",
                                                    ""
                                                )
                                            ),
                                            "destination": destination,
                                        }

                                        st.session_state[
                                            "reset_after_successful_submit"
                                        ] = True

                                    except Exception as refresh_exc:
                                        # POST sudah berhasil; kegagalan refresh
                                        # tidak boleh dianggap sebagai kegagalan
                                        # verifikasi. Pengguna tetap melihat hasil
                                        # pengiriman dan dapat Muat Data manual.
                                        st.session_state[
                                            "post_submit_flash"
                                        ] = None

                            st.rerun()

                        except (
                            SimbaError,
                            LiveVerificationError,
                        ) as exc:
                            st.error(
                                str(exc)
                            )

                        except Exception as exc:
                            st.error(
                                f"Proses verifikasi gagal: {exc}"
                            )

                with no_col:
                    if st.button(
                        "Tidak",
                        use_container_width=True,
                        key=(
                            "confirm_no_"
                            + preview[
                                "application_id"
                            ]
                        ),
                    ):
                        st.rerun()

            # ================================================
            # TOMBOL SIMPAN
            # ================================================

            live_ready = True

            submission_record_now = (
                submission_log.get(
                    institution.application_id
                )
            )

            if execution_mode == "LIVE SIMBA":
                if is_post_transition_state(
                    submission_record_now
                ):
                    live_ready = False
                else:
                    decision_form = form_inspection.get("decisions", {}).get(decision_code, {})
                    live_ready = bool(decision_form.get("ready", False))

            if st.button(
                (
                    "💾 Simpan Hasil Verifikasi"
                    if execution_mode
                    == "DRY RUN"
                    else "🚀 Kirim Hasil Verifikasi ke SIMBA"
                ),
                type="primary",
                key=(
                    "save_verification_"
                    + institution.application_id
                ),
                disabled=(
                    execution_mode
                    == "LIVE SIMBA"
                    and not live_ready
                ),
            ):
                if (
                    execution_mode
                    == "LIVE SIMBA"
                    and not live_ready
                ):
                    st.error(
                        "Struktur form asli SIMBA untuk keputusan ini belum dapat dibuktikan dengan aman. Pengiriman LIVE diblokir."
                    )

                elif (
                    decision_code
                    == "approve"
                    and not review_summary[
                        "all_documents_ok"
                    ]
                ):
                    st.error(
                        "Proposal belum dapat diverifikasi karena masih ada "
                        "dokumen yang belum diperiksa atau perlu perbaikan."
                    )

                elif (
                    is_reject
                    and not verification_note.strip()
                ):
                    st.error(
                        "Catatan Perbaikan wajib diisi untuk proposal "
                        "yang ditolak/dikembalikan."
                    )

                elif (
                    execution_mode
                    == "LIVE SIMBA"
                    and previous_submission
                    and previous_submission.get(
                        "state"
                    )
                    in {
                        "SENT_UNCONFIRMED",
                        "CONFIRMED",
                    }
                ):
                    st.error(
                        "POST ulang diblokir oleh Submission Guard."
                    )

                else:
                    try:
                        before_snapshot = (
                            client.read_target_snapshot(
                                institution=institution
                            )
                        )

                        if not before_snapshot[
                            "safe_identity"
                        ]:
                            st.error(
                                "VALIDASI TARGET GAGAL. Proses dihentikan."
                            )
                            st.json(
                                before_snapshot
                            )

                        else:
                            preview = (
                                client.build_verification_preview(
                                    institution=(
                                        institution
                                    ),
                                    aid_title=(
                                        aid_title
                                    ),
                                    decision=(
                                        decision_code
                                    ),
                                    note=(
                                        verification_note
                                    ),
                                    verification_url=(
                                        verification_url
                                    ),
                                    before_snapshot=(
                                        before_snapshot
                                    ),
                                )
                            )

                            preview[
                                "execution_mode"
                            ] = execution_mode

                            confirm_verification_dialog(
                                preview
                            )

                    except SimbaError as exc:
                        st.error(
                            str(exc)
                        )

            # ================================================
            # HASIL DRY RUN
            # ================================================

            pending = (
                st.session_state.get(
                    "pending_verification"
                )
            )

            check = (
                st.session_state.get(
                    "verification_check"
                )
            )

            live_evidence = (
                st.session_state.get(
                    "live_verification_evidence"
                )
            )

            if (
                pending
                and pending.get(
                    "application_id"
                )
                == institution.application_id
            ):
                st.divider()
                st.subheader(
                    "Hasil Pengiriman"
                )

                if (
                    pending.get(
                        "execution_mode"
                    )
                    == "DRY RUN"
                ):
                    if (
                        check
                        and check.get(
                            "result"
                        )
                        == "DRY_RUN_CONFIRMED"
                    ):
                        st.success(
                            "✅ DRY RUN TERKONFIRMASI"
                        )
                        st.caption(
                            "Target berhasil dibaca ulang dari SIMBA. "
                            "Belum ada perubahan status nyata."
                        )

                    elif check:
                        st.error(
                            "🚨 TARGET TIDAK SESUAI"
                        )

                    with st.container(
                        border=True
                    ):
                        st.write(
                            "**Hasil:**",
                            decision_display(
                                pending[
                                    "decision"
                                ]
                            ),
                        )
                        st.write(
                            "**Nama:**",
                            pending[
                                "institution_name"
                            ],
                        )
                        st.write(
                            "**NSPP:**",
                            pending[
                                "nspp"
                            ],
                        )
                        st.write(
                            "**ID Pengajuan:**",
                            pending[
                                "application_id"
                            ],
                        )
                        if pending.get(
                            "note"
                        ):
                            st.write(
                                "**Catatan:**",
                                pending[
                                    "note"
                                ],
                            )
                        st.write(
                            "**POST ke SIMBA:** TIDAK"
                        )

                else:
                    if live_evidence:
                        result_code = (
                            live_evidence.get(
                                "result"
                            )
                        )

                        expected_status = (
                            live_evidence.get(
                                "expected_status"
                            )
                        )

                        if result_code == "CONFIRMED":
                            if pending.get(
                                "decision"
                            ) == "approve":
                                st.success(
                                    "✅ VERIFIKASI PROPOSAL BERHASIL"
                                )
                                st.write(
                                    "**Status terkonfirmasi:**",
                                    expected_status,
                                )
                            else:
                                destination = (
                                    "Lembaga"
                                    if pending.get(
                                        "decision"
                                    )
                                    == "reject_institution"
                                    else "Kabupaten"
                                )

                                st.success(
                                    "✅ PENOLAKAN BERHASIL DAN TUJUAN TERKONFIRMASI"
                                )
                                st.write(
                                    "**Status:**",
                                    expected_status,
                                )
                                st.write(
                                    "**Dikembalikan ke:**",
                                    destination,
                                )

                                destination_evidence = (
                                    live_evidence.get(
                                        "destination_evidence",
                                        {},
                                    )
                                )

                                st.caption(
                                    "Bukti tujuan: "
                                    + (
                                        destination_evidence.get(
                                            "source",
                                            ""
                                        )
                                        or "SIMBA"
                                    )
                                    + " / "
                                    + (
                                        destination_evidence.get(
                                            "matched_phrase",
                                            ""
                                        )
                                        or "-"
                                    )
                                )

                            st.caption(
                                "Jika URL lama /diverifikasikabupaten/ menjadi 404 "
                                "setelah submit, itu dapat terjadi karena proposal "
                                "sudah berpindah ke jalur /diproseskanwil/."
                            )

                        elif (
                            result_code
                            == "STATUS_CONFIRMED_DESTINATION_UNCONFIRMED"
                        ):
                            destination = (
                                "Lembaga"
                                if pending.get(
                                    "decision"
                                )
                                == "reject_institution"
                                else "Kabupaten"
                            )

                            st.warning(
                                "⚠️ PENOLAKAN BERHASIL, TUJUAN BELUM DAPAT "
                                "DIBUKTIKAN ULANG DARI RESPONSE SIMBA"
                            )
                            st.write(
                                "**Status sudah:**",
                                expected_status,
                            )
                            st.write(
                                "**Tujuan request yang dipilih:**",
                                destination,
                            )
                            st.error(
                                "Jangan kirim ulang proposal. Status penolakan "
                                "sudah berubah; yang belum tersedia hanya bukti "
                                "post-submit yang membedakan tujuan pengembalian."
                            )

                        elif result_code == "STILL_OLD_STATUS":
                            st.error(
                                "❌ STATUS MASIH DIVERIFIKASI KABUPATEN"
                            )
                            st.warning(
                                "POST telah dilakukan, tetapi data yang terbaca "
                                "masih menunjukkan status lama. Jangan klik kirim ulang "
                                "sebelum memeriksa SIMBA."
                            )

                        else:
                            st.warning(
                                "⚠️ POST TERKIRIM, STATUS BELUM TERKONFIRMASI"
                            )
                            st.write(
                                "Jangan melakukan submit ulang. Periksa daftar SIMBA "
                                "terlebih dahulu."
                            )

                        with st.container(
                            border=True
                        ):
                            st.write(
                                "**Keputusan:**",
                                decision_display(
                                    pending[
                                        "decision"
                                    ]
                                ),
                            )
                            st.write(
                                "**Target status:**",
                                expected_status,
                            )
                            st.write(
                                "**HTTP POST:**",
                                live_evidence.get(
                                    "response_status_code"
                                ),
                            )
                            st.write(
                                "**Status dari hasil Kanwil:**",
                                live_evidence.get(
                                    "queue_status"
                                )
                                or (
                                    "Belum ditemukan pada endpoint hasil Kanwil"
                                ),
                            )

                            processed_url = (
                                live_evidence.get(
                                    "processed_ajax_url",
                                    ""
                                )
                            )

                            if processed_url:
                                st.caption(
                                    "Pengecekan dilakukan dengan GET ke endpoint "
                                    "diproseskanwil/data-index."
                                )
                            st.write(
                                "**Status ditemukan di response/detail:**",
                                (
                                    "YA"
                                    if (
                                        live_evidence.get(
                                            "response_contains_expected_status"
                                        )
                                        or live_evidence.get(
                                            "detail_contains_expected_status"
                                        )
                                    )
                                    else "BELUM"
                                ),
                            )

                            st.write(
                                "**Identitas record sama:**",
                                (
                                    "YA"
                                    if live_evidence.get(
                                        "queue_identity_match"
                                    )
                                    else (
                                        "TIDAK DAPAT DICEK"
                                        if not live_evidence.get(
                                            "queue_record_found"
                                        )
                                        else "TIDAK"
                                    )
                                ),
                            )

                            if pending.get(
                                "decision"
                            ) in {
                                "reject_institution",
                                "reject_district",
                            }:
                                destination_evidence = (
                                    live_evidence.get(
                                        "destination_evidence",
                                        {},
                                    )
                                )
                                note_evidence = (
                                    live_evidence.get(
                                        "note_evidence",
                                        {},
                                    )
                                )

                                st.write(
                                    "**Tujuan penolakan terkonfirmasi:**",
                                    (
                                        "YA"
                                        if destination_evidence.get(
                                            "confirmed"
                                        )
                                        else "BELUM"
                                    ),
                                )

                                st.write(
                                    "**Catatan perbaikan terbaca kembali:**",
                                    (
                                        "YA"
                                        if note_evidence.get(
                                            "confirmed"
                                        )
                                        else "BELUM"
                                    ),
                                )

                        with st.expander(
                            "Detail bukti verifikasi",
                            expanded=False,
                        ):
                            safe_evidence = dict(
                                live_evidence
                            )
                            st.json(
                                safe_evidence
                            )
