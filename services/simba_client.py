from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils.helpers import (
    abs_url,
    clean_text,
    extract_data_file,
    extract_data_name,
    extract_first_href,
)


@dataclass
class Institution:
    application_id: str
    pesantren_id: str
    number: str
    nspp: str
    name: str
    province: str
    address: str
    submission_date: str
    status: str
    district_note: str
    detail_url: str
    aid_category_id: str = ""
    aid_title: str = ""
    recommendation_url: str = ""
    recommendation_path: str = ""


@dataclass
class ProposalDocument:
    id: str
    proposal_id: str
    category_id: str
    number: str
    stage: str
    name: str
    file_name: str
    file_url: str
    file_type: str
    size: str
    date: str
    score: str
    is_document_valid: object
    text_value: str = ""


class SimbaError(RuntimeError):
    pass


class SimbaClient:
    def __init__(
        self,
        base_url: str,
        cookie_header: str,
        user_agent: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "*/*",
                "User-Agent": user_agent or (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/152.0.0.0 Safari/537.36"
                ),
                "Referer": self.base_url + "/",
            }
        )

        self._apply_cookie_header(
            cookie_header
        )

    def _apply_cookie_header(
        self,
        cookie_header: str,
    ) -> None:
        if not cookie_header:
            return

        for item in cookie_header.split(";"):
            item = item.strip()

            if (
                not item
                or "=" not in item
            ):
                continue

            name, value = item.split(
                "=",
                1,
            )

            name = name.strip()
            value = value.strip()

            if name:
                self.session.cookies.set(
                    name,
                    value,
                )

    def make_url(
        self,
        path_or_url: str,
    ) -> str:
        if not path_or_url:
            return self.base_url

        path_or_url = (
            str(path_or_url)
            .replace("\\/", "/")
            .strip()
        )

        if path_or_url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return path_or_url

        return urljoin(
            self.base_url + "/",
            path_or_url.lstrip("/"),
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params=None,
        data=None,
        headers=None,
        timeout: int = 60,
    ) -> requests.Response:
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            )

        except requests.Timeout as exc:
            raise SimbaError(
                "Koneksi ke SIMBA timeout."
            ) from exc

        except requests.ConnectionError as exc:
            raise SimbaError(
                "Tidak dapat terhubung ke server SIMBA."
            ) from exc

        except requests.RequestException as exc:
            raise SimbaError(
                f"Request SIMBA gagal: {exc}"
            ) from exc

        if response.status_code == 401:
            raise SimbaError(
                "Session SIMBA tidak valid atau sudah kedaluwarsa."
            )

        if response.status_code == 403:
            raise SimbaError(
                "Akses SIMBA ditolak (403)."
            )

        if response.status_code == 404:
            raise SimbaError(
                "Halaman/endpoint tidak ditemukan (404): "
                f"{response.url}"
            )

        if response.status_code >= 500:
            raise SimbaError(
                "Server SIMBA mengalami error "
                f"({response.status_code})."
            )

        if response.status_code >= 400:
            raise SimbaError(
                f"HTTP {response.status_code}\n\n"
                f"URL:\n{response.url}\n\n"
                f"Response:\n{response.text[:1000]}"
            )

        if "/login" in response.url.lower():
            raise SimbaError(
                "Request diarahkan ke halaman login. "
                "Session SIMBA kemungkinan sudah habis."
            )

        return response

    def get_html(
        self,
        path_or_url: str,
    ) -> tuple[str, str]:
        url = self.make_url(
            path_or_url
        )

        response = self._request(
            "GET",
            url,
        )

        return (
            response.text,
            response.url,
        )

    def get_soup(
        self,
        path_or_url: str,
    ) -> tuple[BeautifulSoup, str]:
        html_text, final_url = (
            self.get_html(
                path_or_url
            )
        )

        return (
            BeautifulSoup(
                html_text,
                "lxml",
            ),
            final_url,
        )

    def request_datatable(
        self,
        url: str,
        *,
        method: str = "GET",
        page_size: int = 500,
        extra_params: Optional[dict] = None,
    ) -> tuple[dict, str]:
        method = method.upper().strip()

        if method not in {
            "GET",
            "POST",
        }:
            raise SimbaError(
                "Method DataTables harus GET atau POST."
            )

        params = {
            "draw": 1,
            "start": 0,
            "length": int(page_size),
        }

        if extra_params:
            params.update(
                extra_params
            )

        headers = {
            "Accept": (
                "application/json, "
                "text/javascript, "
                "*/*; q=0.01"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url + "/",
        }

        final_url = self.make_url(
            url
        )

        if method == "GET":
            response = self._request(
                "GET",
                final_url,
                params=params,
                headers=headers,
            )
        else:
            response = self._request(
                "POST",
                final_url,
                data=params,
                headers=headers,
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise SimbaError(
                "Response DataTables bukan JSON.\n\n"
                f"Final URL:\n{response.url}\n\n"
                f"Content-Type:\n"
                f"{response.headers.get('Content-Type')}\n\n"
                f"Response awal:\n"
                f"{response.text[:1500]}"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise SimbaError(
                "Response JSON bukan object."
            )

        return (
            payload,
            response.url,
        )

    def list_institutions_ajax(
        self,
        ajax_url: str,
        *,
        method: str = "GET",
        page_size: int = 500,
        extra_params: Optional[dict] = None,
    ) -> tuple[list[Institution], dict]:
        if not ajax_url:
            raise SimbaError(
                "Request URL AJAX Lembaga belum diisi."
            )

        payload, final_url = (
            self.request_datatable(
                ajax_url,
                method=method,
                page_size=page_size,
                extra_params=extra_params,
            )
        )

        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            raise SimbaError(
                "Field data daftar lembaga bukan list."
            )

        institutions = []

        for index, row in enumerate(
            rows,
            start=1,
        ):
            if not isinstance(
                row,
                dict,
            ):
                continue

            options_html = (
                row.get("options")
                or ""
            )

            detail_href = (
                extract_first_href(
                    options_html
                )
            )

            recommendation_html = (
                row.get(
                    "surat_rekomendasi_kab"
                )
                or ""
            )

            recommendation_href = (
                extract_first_href(
                    recommendation_html
                )
            )

            aid_title = clean_text(
                row.get(
                    "kategori_bantuan"
                )
                or row.get(
                    "nama_kategori_bantuan"
                )
                or row.get(
                    "nama_bantuan"
                )
                or row.get(
                    "judul_bantuan"
                )
                or ""
            )

            institutions.append(
                Institution(
                    application_id=str(
                        row.get("id")
                        or ""
                    ),
                    pesantren_id=str(
                        row.get("pesantren_id")
                        or ""
                    ),
                    number=str(
                        row.get("DT_Row_Index")
                        or index
                    ),
                    nspp=clean_text(
                        row.get("nspp")
                    ),
                    name=clean_text(
                        row.get("pesantren")
                    ),
                    province=clean_text(
                        row.get("provinsi")
                    ),
                    address=clean_text(
                        row.get("alamat")
                    ),
                    submission_date=clean_text(
                        row.get("tanggal_pengajuan")
                        or row.get("tanggal")
                    ),
                    status=clean_text(
                        row.get("status")
                    ),
                    district_note=clean_text(
                        row.get("catatan_kabupaten")
                        or row.get("catatan")
                        or "-"
                    ),
                    detail_url=abs_url(
                        self.base_url,
                        detail_href,
                    ),
                    aid_category_id=str(
                        row.get("kategori_bantuan_id")
                        or ""
                    ),
                    aid_title=aid_title,
                    recommendation_url=abs_url(
                        self.base_url,
                        recommendation_href,
                    ),
                    recommendation_path=clean_text(
                        row.get(
                            "path_rekomendasi_kabupaten"
                        )
                    ),
                )
            )

        meta = {
            "draw": payload.get("draw"),
            "recordsTotal": payload.get(
                "recordsTotal",
                len(institutions),
            ),
            "recordsFiltered": payload.get(
                "recordsFiltered",
                len(institutions),
            ),
            "loaded": len(
                institutions
            ),
            "final_url": final_url,
        }

        return (
            institutions,
            meta,
        )

    def detail_url_candidates(
        self,
        detail_url: str,
        *,
        prefer_processed: bool = False,
    ) -> list[str]:
        """
        Kandidat URL detail yang aman untuk masa transisi status.

        Saat proposal berpindah dari Diverifikasi Kabupaten ke hasil Kanwil,
        route lama /diverifikasikabupaten/... dapat menjadi 404 dan route
        baru berpindah ke /diproseskanwil/....

        Tidak ada POST di method ini; hanya membentuk kandidat GET.
        """
        url = self.make_url(
            detail_url
        )

        candidates = []

        processed_url = ""

        if (
            "/diverifikasikabupaten/"
            in url
        ):
            processed_url = url.replace(
                "/diverifikasikabupaten/",
                "/diproseskanwil/",
            )

        if (
            prefer_processed
            and processed_url
        ):
            candidates.append(
                processed_url
            )

        candidates.append(
            url
        )

        if (
            processed_url
            and processed_url
            not in candidates
        ):
            candidates.append(
                processed_url
            )

        return candidates

    def resolve_detail_url(
        self,
        detail_url: str,
        *,
        prefer_processed: bool = False,
    ) -> tuple[str, str]:
        """
        Cari URL detail yang masih valid dengan GET-only.

        Return:
            (resolved_url, html_text)
        """
        errors = []

        for candidate in self.detail_url_candidates(
            detail_url,
            prefer_processed=prefer_processed,
        ):
            try:
                html_text, final_url = (
                    self.get_html(
                        candidate
                    )
                )

                return (
                    final_url,
                    html_text,
                )

            except SimbaError as exc:
                errors.append(
                    f"{candidate} -> {exc}"
                )

        raise SimbaError(
            "Tidak dapat menemukan URL detail aktif setelah "
            "perubahan status proposal. "
            "Route lama kemungkinan sudah berpindah.\\n\\n"
            + "\\n".join(
                errors
            )
        )

    def discover_institution_links_resilient(
        self,
        detail_url: str,
        *,
        prefer_processed: bool = False,
    ) -> dict:
        """
        Versi tahan-transisi dari discover_institution_links().
        """
        resolved_url, html_text = (
            self.resolve_detail_url(
                detail_url,
                prefer_processed=prefer_processed,
            )
        )

        soup = BeautifulSoup(
            html_text,
            "lxml",
        )

        result = {
            "detail_url": resolved_url,
            "profile_url": resolved_url,
            "proposal_review_url": "",
            "verification_url": "",
        }

        for element in soup.select(
            "a[href]"
        ):
            href = (
                element.get("href")
                or ""
            ).strip()

            if not href:
                continue

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            ).lower()

            href_lower = (
                href.lower()
            )

            full_url = abs_url(
                self.base_url,
                href,
            )

            if (
                "review proposal" in text
                or "show-file-proposal"
                in href_lower
                or "file-proposal"
                in href_lower
            ):
                result[
                    "proposal_review_url"
                ] = full_url

            if (
                "hasil verifikasi" in text
                or "hasil-verifikasi"
                in href_lower
            ):
                result[
                    "verification_url"
                ] = full_url

        return result

    def discover_institution_links(
        self,
        detail_url: str,
    ) -> dict:
        soup, final_url = (
            self.get_soup(
                detail_url
            )
        )

        result = {
            "detail_url": final_url,
            "profile_url": final_url,
            "proposal_review_url": "",
            "verification_url": "",
        }

        for element in soup.select(
            "a[href]"
        ):
            href = (
                element.get("href")
                or ""
            ).strip()

            if not href:
                continue

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            ).lower()

            href_lower = (
                href.lower()
            )

            full_url = abs_url(
                self.base_url,
                href,
            )

            if (
                "review proposal" in text
                or "show-file-proposal"
                in href_lower
                or "file-proposal"
                in href_lower
            ):
                result[
                    "proposal_review_url"
                ] = full_url

            if (
                "hasil verifikasi" in text
                or "hasil-verifikasi"
                in href_lower
            ):
                result[
                    "verification_url"
                ] = full_url

        return result

    def discover_aid_title(
        self,
        detail_url: str,
    ) -> str:
        soup, _ = self.get_soup(
            detail_url
        )

        selectors = [
            ".breadcrumb li",
            ".breadcrumb-item",
            "h1",
            "h2",
            "h3",
            "h4",
            ".ibox-title h5",
            ".panel-title",
        ]

        candidates = []

        for selector in selectors:
            for element in soup.select(
                selector
            ):
                text = clean_text(
                    element.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    text
                    and "bantuan"
                    in text.lower()
                    and len(text) <= 250
                ):
                    candidates.append(
                        text
                    )

        if candidates:
            return max(
                candidates,
                key=len,
            )

        return ""

    def parse_profile(
        self,
        url: str,
    ) -> dict:
        if not url:
            return {}

        soup, _ = self.get_soup(
            url
        )

        profile = {}

        for row in soup.select(
            "table tr"
        ):
            cells = row.find_all(
                [
                    "th",
                    "td",
                ]
            )

            if len(cells) < 2:
                continue

            key = clean_text(
                cells[0].get_text(
                    " ",
                    strip=True,
                )
            ).rstrip(":")

            value = clean_text(
                cells[-1].get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                key
                and value
                and len(key) <= 100
            ):
                profile.setdefault(
                    key,
                    value,
                )

        return profile

    def get_proposal_completeness(
        self,
        review_url: str,
    ) -> dict:
        soup, _ = self.get_soup(
            review_url
        )

        text = clean_text(
            soup.get_text(
                " ",
                strip=True,
            )
        )

        match = re.search(
            (
                r"Kelengkapan\s+"
                r"Persyaratan\s*:\s*"
                r"(\d+)\s+dari\s+(\d+)"
            ),
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return {
                "completed": None,
                "total": None,
                "text": "",
            }

        completed = int(
            match.group(1)
        )

        total = int(
            match.group(2)
        )

        return {
            "completed": completed,
            "total": total,
            "text": (
                f"{completed} dari {total}"
            ),
        }

    def discover_review_ajax_urls(
        self,
        review_url: str,
    ) -> list[str]:
        html_text, _ = self.get_html(
            review_url
        )

        candidates = []

        patterns = [
            r"""ajax\s*:\s*['"]([^'"]+)['"]""",
            r"""ajax\s*:\s*\{[\s\S]*?url\s*:\s*['"]([^'"]+)['"]""",
            r"""url\s*:\s*['"]([^'"]+)['"]""",
        ]

        for pattern in patterns:
            for match in re.findall(
                pattern,
                html_text,
                flags=re.IGNORECASE,
            ):
                value = (
                    str(match)
                    .replace("\\/", "/")
                    .strip()
                )

                if not value:
                    continue

                full_url = (
                    self.make_url(
                        value
                    )
                )

                low = (
                    full_url.lower()
                )

                if (
                    "proposal" in low
                    or "file" in low
                    or "dokumen" in low
                    or "verifikasi" in low
                ):
                    if (
                        full_url
                        not in candidates
                    ):
                        candidates.append(
                            full_url
                        )

        return candidates

    def _documents_from_payload(
        self,
        payload: dict,
    ) -> list[ProposalDocument]:
        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            return []

        documents = []

        for index, row in enumerate(
            rows,
            start=1,
        ):
            if not isinstance(
                row,
                dict,
            ):
                continue

            options_html = (
                row.get("options")
                or ""
            )

            name = clean_text(
                row.get("kategori_file")
                or row.get("jenis")
                or extract_data_name(
                    options_html
                )
            )

            if not name:
                continue

            file_type = clean_text(
                row.get("file_type")
                or row.get("type")
            ).lower()

            file_url = ""
            text_value = ""

            if file_type == "pdf":
                file_url = (
                    extract_data_file(
                        options_html
                    )
                )

            elif (
                "data-file"
                in str(
                    options_html
                )
            ):
                file_url = (
                    extract_data_file(
                        options_html
                    )
                )

                if file_url:
                    file_type = "pdf"

            if file_type == "text":
                text_value = clean_text(
                    row.get("value")
                    or row.get("options")
                    or ""
                )

            documents.append(
                ProposalDocument(
                    id=str(
                        row.get("id")
                        or ""
                    ),
                    proposal_id=str(
                        row.get("proposal_id")
                        or ""
                    ),
                    category_id=str(
                        row.get("kategori_file_id")
                        or ""
                    ),
                    number=str(
                        row.get("DT_Row_Index")
                        or index
                    ),
                    stage=clean_text(
                        row.get("nama_tahap")
                    ),
                    name=name,
                    file_name=clean_text(
                        row.get("file_path")
                    ),
                    file_url=file_url,
                    file_type=file_type,
                    size=clean_text(
                        row.get("size")
                    ),
                    date=clean_text(
                        row.get("tanggal")
                        or row.get("created_at")
                    ),
                    score=clean_text(
                        row.get("skor")
                    ),
                    is_document_valid=(
                        row.get("is_dokumen_sesuai")
                    ),
                    text_value=text_value,
                )
            )

        def sort_key(
            item: ProposalDocument,
        ):
            try:
                return int(
                    item.number
                )
            except (
                TypeError,
                ValueError,
            ):
                return 999999

        documents.sort(
            key=sort_key
        )

        return documents

    def _document_payload_score(
        self,
        payload: dict,
    ) -> int:
        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            return 0

        score = 0

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                continue

            if "kategori_file_id" in row:
                score += 5
            if "kategori_file" in row:
                score += 5
            if "file_type" in row:
                score += 4
            if "proposal_id" in row:
                score += 3
            if "nama_tahap" in row:
                score += 2
            if "file_path" in row:
                score += 2
            if "value" in row:
                score += 1
            if "options" in row:
                score += 1

        return score

    def list_proposal_documents_auto(
        self,
        review_url: str,
        *,
        explicit_ajax_url: str = "",
        method: str = "GET",
        page_size: int = 500,
        extra_params: Optional[dict] = None,
    ) -> tuple[list[ProposalDocument], dict]:
        candidates = []

        if explicit_ajax_url:
            candidates.append(
                self.make_url(
                    explicit_ajax_url
                )
            )

        for url in (
            self.discover_review_ajax_urls(
                review_url
            )
        ):
            if url not in candidates:
                candidates.append(
                    url
                )

        errors = []
        attempts = []
        valid_results = []

        for candidate in candidates:
            try:
                payload, final_url = (
                    self.request_datatable(
                        candidate,
                        method=method,
                        page_size=page_size,
                        extra_params=extra_params,
                    )
                )

            except SimbaError as exc:
                errors.append(
                    {
                        "url": candidate,
                        "error": str(exc),
                    }
                )
                continue

            documents = (
                self._documents_from_payload(
                    payload
                )
            )

            score = (
                self._document_payload_score(
                    payload
                )
            )

            records_total = payload.get(
                "recordsTotal",
                len(documents),
            )

            try:
                records_total = int(
                    records_total
                )
            except (
                TypeError,
                ValueError,
            ):
                records_total = len(
                    documents
                )

            attempts.append(
                {
                    "url": final_url,
                    "recordsTotal": records_total,
                    "documents": len(documents),
                    "score": score,
                }
            )

            if (
                documents
                and score > 0
            ):
                valid_results.append(
                    {
                        "url": final_url,
                        "payload": payload,
                        "documents": documents,
                        "recordsTotal": records_total,
                        "score": score,
                    }
                )

        if not valid_results:
            return (
                [],
                {
                    "ajax_url": "",
                    "recordsTotal": 0,
                    "recordsFiltered": 0,
                    "loaded": 0,
                    "candidates": candidates,
                    "attempts": attempts,
                    "errors": errors,
                },
            )

        best = max(
            valid_results,
            key=lambda item: (
                item["recordsTotal"],
                len(
                    item["documents"]
                ),
                item["score"],
            ),
        )

        documents = (
            best["documents"]
        )

        payload = (
            best["payload"]
        )

        return (
            documents,
            {
                "ajax_url": best["url"],
                "recordsTotal": payload.get(
                    "recordsTotal",
                    len(documents),
                ),
                "recordsFiltered": payload.get(
                    "recordsFiltered",
                    len(documents),
                ),
                "loaded": len(documents),
                "candidates": candidates,
                "attempts": attempts,
                "errors": errors,
            },
        )

    def fetch_document(
        self,
        url: str,
        timeout: int = 90,
    ):
        if not url:
            raise SimbaError(
                "URL dokumen kosong."
            )

        response = self._request(
            "GET",
            url,
            timeout=timeout,
        )

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            or ""
        ).lower()

        return (
            response.content,
            content_type,
            response.url,
        )

    def read_target_snapshot(
        self,
        *,
        institution: Institution,
    ) -> dict:
        """
        Membaca ulang target dari SIMBA tanpa mengubah data.
        Snapshot ini dipakai untuk membuktikan bahwa target
        yang dibaca adalah proposal yang sama.
        """
        if not institution.detail_url:
            raise SimbaError(
                "URL Detail lembaga kosong."
            )

        soup, final_url = (
            self.get_soup(
                institution.detail_url
            )
        )

        page_text = clean_text(
            soup.get_text(
                " ",
                strip=True,
            )
        )

        application_id = (
            institution.application_id
            or ""
        ).strip()

        nspp = (
            institution.nspp
            or ""
        ).strip()

        institution_name = (
            institution.name
            or ""
        ).strip()

        status = (
            institution.status
            or ""
        ).strip()

        application_match = (
            bool(application_id)
            and (
                application_id in final_url
                or application_id in page_text
            )
        )

        nspp_match = (
            bool(nspp)
            and nspp in page_text
        )

        name_match = (
            bool(institution_name)
            and institution_name.lower()
            in page_text.lower()
        )

        # Status dari list belum tentu ada sebagai field khusus di halaman detail.
        # Kita hanya tandai apakah teks status lama terlihat di halaman.
        status_visible = (
            bool(status)
            and status.lower()
            in page_text.lower()
        )

        return {
            "application_id": application_id,
            "nspp": nspp,
            "institution_name": institution_name,
            "status_from_list": status,
            "application_id_match": application_match,
            "nspp_match": nspp_match,
            "institution_name_match": name_match,
            "status_visible_on_detail": status_visible,
            "detail_url": final_url,
            "safe_identity": (
                nspp_match
                and name_match
            ),
        }

    def verify_target_identity(
        self,
        *,
        institution: Institution,
        detail_url: str,
    ) -> dict:
        if not detail_url:
            raise SimbaError(
                "URL Detail lembaga kosong."
            )

        snapshot = self.read_target_snapshot(
            institution=institution
        )

        return {
            "application_id_match": snapshot[
                "application_id_match"
            ],
            "nspp_match": snapshot[
                "nspp_match"
            ],
            "institution_name_match": snapshot[
                "institution_name_match"
            ],
            "final_url": snapshot[
                "detail_url"
            ],
            "safe": snapshot[
                "safe_identity"
            ],
        }

    def build_verification_preview(
        self,
        *,
        institution: Institution,
        aid_title: str,
        decision: str,
        note: str = "",
        verification_url: str = "",
        before_snapshot: Optional[dict] = None,
    ) -> dict:
        application_id = (
            institution.application_id
            or ""
        ).strip()

        nspp = (
            institution.nspp
            or ""
        ).strip()

        institution_name = (
            institution.name
            or ""
        ).strip()

        if not application_id:
            raise SimbaError(
                "ID Pengajuan kosong."
            )

        if not nspp:
            raise SimbaError(
                "NSPP kosong."
            )

        if not institution_name:
            raise SimbaError(
                "Nama lembaga kosong."
            )

        allowed_decisions = {
            "approve",
            "reject_institution",
            "reject_district",
        }

        if decision not in (
            allowed_decisions
        ):
            raise SimbaError(
                "Keputusan verifikasi tidak valid."
            )

        if (
            decision
            in {
                "reject_institution",
                "reject_district",
            }
            and not note.strip()
        ):
            raise SimbaError(
                "Catatan wajib diisi "
                "untuk pengembalian proposal."
            )

        destination_map = {
            "approve": "Admin Pusat",
            "reject_institution": "Lembaga",
            "reject_district": "Kabupaten",
        }

        return {
            "application_id": application_id,
            "nspp": nspp,
            "institution_name": institution_name,
            "aid_category_id": (
                institution.aid_category_id
            ),
            "aid_title": aid_title,
            "decision": decision,
            "destination": (
                destination_map[
                    decision
                ]
            ),
            "note": note.strip(),
            "verification_url": verification_url,
            "before_snapshot": before_snapshot or {},
            "dry_run": True,
        }

    def confirm_dry_run_result(
        self,
        *,
        institution: Institution,
        before_snapshot: dict,
    ) -> dict:
        """
        GET ulang proposal setelah DRY RUN.
        Karena DRY RUN tidak melakukan POST, status memang
        seharusnya tidak berubah. Yang diperiksa di sini:
        - target masih proposal yang sama
        - identitas masih cocok
        - tidak ada perubahan nyata akibat aplikasi
        """
        after_snapshot = (
            self.read_target_snapshot(
                institution=institution
            )
        )

        same_application = (
            before_snapshot.get(
                "application_id"
            )
            == after_snapshot.get(
                "application_id"
            )
        )

        same_nspp = (
            before_snapshot.get(
                "nspp"
            )
            == after_snapshot.get(
                "nspp"
            )
        )

        same_name = (
            before_snapshot.get(
                "institution_name"
            )
            == after_snapshot.get(
                "institution_name"
            )
        )

        same_status = (
            before_snapshot.get(
                "status_from_list"
            )
            == after_snapshot.get(
                "status_from_list"
            )
        )

        target_safe = (
            after_snapshot.get(
                "safe_identity",
                False,
            )
            and same_application
            and same_nspp
            and same_name
        )

        return {
            "target_safe": target_safe,
            "same_application": same_application,
            "same_nspp": same_nspp,
            "same_name": same_name,
            "same_status": same_status,
            "before": before_snapshot,
            "after": after_snapshot,
            "real_submission_performed": False,
            "result": (
                "DRY_RUN_CONFIRMED"
                if target_safe
                else "TARGET_MISMATCH"
            ),
        }
