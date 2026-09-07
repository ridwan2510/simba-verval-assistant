from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from utils.helpers import clean_text


class LiveVerificationError(RuntimeError):
    pass


def _norm(value: str) -> str:
    return " ".join(
        clean_text(value or "")
        .lower()
        .replace("–", "-")
        .replace("—", "-")
        .split()
    )


def _decision_from_text(text: str) -> Optional[str]:
    t = _norm(text)

    reject_words = (
        "tolak",
        "revisi",
        "kembali",
        "kembalikan",
        "dikembalikan",
        "pengembalian",
    )

    if (
        "lembaga" in t
        and any(word in t for word in reject_words)
    ):
        return "reject_institution"

    if (
        (
            "kabupaten" in t
            or "kab/kota" in t
            or "kabupaten/kota" in t
        )
        and any(word in t for word in reject_words)
    ):
        return "reject_district"

    if (
        "verifikasi proposal" in t
        or "terima proposal" in t
        or "menerima proposal" in t
        or "ajukan proposal" in t
    ) and "tolak" not in t:
        return "approve"

    return None


def _sensitive_field_name(name: str) -> bool:
    n = (name or "").lower()
    return any(
        marker in n
        for marker in (
            "token",
            "csrf",
            "xsrf",
            "session",
            "authorization",
            "cookie",
        )
    )


@dataclass
class SubmissionEvidence:
    expected_status: str
    response_status_code: int
    response_final_url: str
    response_contains_expected_status: bool
    response_contains_old_status: bool
    detail_contains_expected_status: bool
    detail_final_url: str
    queue_record_found: bool
    queue_status: str
    queue_expected_status: bool
    queue_old_status: bool
    confirmed: bool
    result: str


class SubmissionLog:
    """
    Guard lokal untuk mencegah POST ganda tanpa sengaja.
    Record disimpan per application_id.
    """

    def __init__(self, path: str = "data/submission_log.json"):
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _load(self) -> dict:
        if not self.path.exists():
            return {}

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if isinstance(data, dict):
                return data

        except Exception:
            pass

        return {}

    def _save(self, data: dict) -> None:
        tmp = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        with tmp.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        tmp.replace(
            self.path
        )

    def get(self, application_id: str) -> Optional[dict]:
        return self._load().get(
            str(application_id)
        )

    def record(
        self,
        application_id: str,
        *,
        decision: str,
        state: str,
        response_status_code: Optional[int] = None,
        result: Optional[dict] = None,
    ) -> dict:
        data = self._load()

        record = {
            "application_id": str(
                application_id
            ),
            "decision": decision,
            "state": state,
            "updated_at": (
                datetime.now()
                .astimezone()
                .isoformat(
                    timespec="seconds"
                )
            ),
            "response_status_code": (
                response_status_code
            ),
            "result": result or {},
        }

        data[
            str(application_id)
        ] = record

        self._save(
            data
        )

        return record

    def clear(
        self,
        application_id: str,
    ) -> None:
        data = self._load()

        data.pop(
            str(application_id),
            None,
        )

        self._save(
            data
        )


class VerificationFormEngine:
    """
    Mesin live yang TIDAK menebak endpoint/payload.

    Endpoint, method, nama field, hidden input, radio/select value,
    dan CSRF dibaca dari halaman Hasil Verifikasi SIMBA yang sedang aktif.
    Bila struktur halaman tidak cukup jelas, live submit diblokir.
    """

    EXPECTED_STATUS = {
        "approve": "Diverifikasi Kanwil",
        "reject_institution": "Ditolak Kanwil",
        "reject_district": "Ditolak kanwil ke kabupaten",
    }

    EXPECTED_STATUS_VARIANTS = {
        "approve": (
            "Diverifikasi Kanwil",
        ),
        "reject_institution": (
            "Ditolak Kanwil",
            "Ditolak kanwil ke lembaga",
        ),
        "reject_district": (
            "Ditolak kanwil ke kabupaten",
            "Ditolak Kanwil",
        ),
    }

    OLD_STATUS = "Diverifikasi Kabupaten"

    def __init__(
        self,
        client,
        submission_log: Optional[SubmissionLog] = None,
    ):
        self.client = client
        self.submission_log = (
            submission_log
            or SubmissionLog()
        )

    def _absolute_url(
        self,
        base_url: str,
        value: str,
    ) -> str:
        if not value:
            return base_url

        return urljoin(
            base_url,
            value,
        )

    def _control_label(
        self,
        form,
        element,
    ) -> str:
        candidates = []

        def add_candidate(value):
            text = clean_text(value or "")
            if text and text not in candidates:
                candidates.append(text)

        for attr in (
            "aria-label",
            "title",
            "data-label",
            "data-title",
        ):
            add_candidate(
                element.get(attr, "")
            )

        element_id = (
            element.get("id")
            or ""
        )

        if element_id:
            label = form.find(
                "label",
                attrs={
                    "for": element_id
                },
            )

            if label:
                add_candidate(
                    label.get_text(
                        " ",
                        strip=True,
                    )
                )

        parent_label = element.find_parent(
            "label"
        )

        if parent_label:
            add_candidate(
                parent_label.get_text(
                    " ",
                    strip=True,
                )
            )

        for sibling in (
            element.find_previous_sibling(),
            element.find_next_sibling(),
        ):
            if sibling:
                try:
                    add_candidate(
                        sibling.get_text(
                            " ",
                            strip=True,
                        )
                    )
                except Exception:
                    add_candidate(
                        str(sibling)
                    )

        parent = element.parent
        depth = 0

        while (
            parent
            and parent != form
            and depth < 4
        ):
            try:
                wrapper_text = clean_text(
                    parent.get_text(
                        " ",
                        strip=True,
                    )
                )

                if (
                    wrapper_text
                    and len(wrapper_text) <= 500
                ):
                    add_candidate(
                        wrapper_text
                    )
            except Exception:
                pass

            parent = parent.parent
            depth += 1

        for text in candidates:
            if _decision_from_text(text):
                return text

        return (
            candidates[0]
            if candidates
            else ""
        )

    def _form_controls(
        self,
        form,
    ) -> list[tuple[str, str]]:
        """
        Meniru successful controls pada form browser.
        Radio tidak dipilih tidak ikut.
        Checkbox hanya yang checked.
        Disabled tidak ikut.
        Submit button ditambahkan terpisah sesuai pilihan aksi.
        """
        controls: list[
            tuple[str, str]
        ] = []

        for element in form.find_all(
            [
                "input",
                "textarea",
                "select",
            ]
        ):
            if element.has_attr(
                "disabled"
            ):
                continue

            name = (
                element.get("name")
                or ""
            ).strip()

            if not name:
                continue

            tag = element.name.lower()

            if tag == "input":
                input_type = (
                    element.get(
                        "type",
                        "text",
                    )
                    or "text"
                ).lower()

                if input_type in {
                    "submit",
                    "button",
                    "reset",
                    "file",
                    "image",
                }:
                    continue

                if input_type in {
                    "radio",
                    "checkbox",
                }:
                    if not element.has_attr(
                        "checked"
                    ):
                        continue

                controls.append(
                    (
                        name,
                        str(
                            element.get(
                                "value",
                                "",
                            )
                            or ""
                        ),
                    )
                )

            elif tag == "textarea":
                controls.append(
                    (
                        name,
                        element.get_text()
                        or "",
                    )
                )

            elif tag == "select":
                selected = element.find_all(
                    "option",
                    selected=True,
                )

                if not selected:
                    first = element.find(
                        "option"
                    )
                    selected = (
                        [first]
                        if first
                        else []
                    )

                for option in selected:
                    controls.append(
                        (
                            name,
                            str(
                                option.get(
                                    "value",
                                    "",
                                )
                                or ""
                            ),
                        )
                    )

        return controls

    def _parse_form(
        self,
        form,
        *,
        page_url: str,
        form_index: int,
    ) -> dict:
        method = (
            form.get(
                "method",
                "GET",
            )
            or "GET"
        ).upper()

        action_url = (
            self._absolute_url(
                page_url,
                form.get(
                    "action",
                    "",
                )
                or page_url,
            )
        )

        enctype = (
            form.get(
                "enctype",
                "application/x-www-form-urlencoded",
            )
            or "application/x-www-form-urlencoded"
        ).lower()

        choices = []

        for element in form.find_all(
            "input"
        ):
            if element.has_attr(
                "disabled"
            ):
                continue

            input_type = (
                element.get(
                    "type",
                    "text",
                )
                or "text"
            ).lower()

            if input_type != "radio":
                continue

            name = (
                element.get("name")
                or ""
            ).strip()

            if not name:
                continue

            label = self._control_label(
                form,
                element,
            )

            choices.append(
                {
                    "kind": "radio",
                    "field": name,
                    "value": str(
                        element.get(
                            "value",
                            "",
                        )
                        or ""
                    ),
                    "label": label,
                    "decision": (
                        _decision_from_text(
                            label
                        )
                    ),
                }
            )

        for select in form.find_all(
            "select"
        ):
            if select.has_attr(
                "disabled"
            ):
                continue

            name = (
                select.get("name")
                or ""
            ).strip()

            if not name:
                continue

            for option in select.find_all(
                "option"
            ):
                label = clean_text(
                    option.get_text(
                        " ",
                        strip=True,
                    )
                )

                decision = (
                    _decision_from_text(
                        label
                    )
                )

                if decision:
                    choices.append(
                        {
                            "kind": "select",
                            "field": name,
                            "value": str(
                                option.get(
                                    "value",
                                    "",
                                )
                                or ""
                            ),
                            "label": label,
                            "decision": decision,
                        }
                    )

        for button in form.find_all(
            [
                "button",
                "input",
            ]
        ):
            if button.has_attr(
                "disabled"
            ):
                continue

            if button.name == "input":
                input_type = (
                    button.get(
                        "type",
                        ""
                    )
                    or ""
                ).lower()

                if input_type != "submit":
                    continue

                label = clean_text(
                    button.get(
                        "value",
                        ""
                    )
                )

            else:
                button_type = (
                    button.get(
                        "type",
                        "submit",
                    )
                    or "submit"
                ).lower()

                if button_type != "submit":
                    continue

                label = clean_text(
                    button.get_text(
                        " ",
                        strip=True,
                    )
                    or button.get(
                        "value",
                        ""
                    )
                )

            decision = (
                _decision_from_text(
                    label
                )
            )

            name = (
                button.get("name")
                or ""
            ).strip()

            value = str(
                button.get(
                    "value",
                    ""
                )
                or ""
            )

            if decision and name:
                choices.append(
                    {
                        "kind": "submit",
                        "field": name,
                        "value": value,
                        "label": label,
                        "decision": decision,
                    }
                )

        note_candidates = []

        for textarea in form.find_all(
            "textarea"
        ):
            if textarea.has_attr(
                "disabled"
            ):
                continue

            name = (
                textarea.get("name")
                or ""
            ).strip()

            if not name:
                continue

            label = self._control_label(
                form,
                textarea,
            )

            note_candidates.append(
                {
                    "field": name,
                    "label": label,
                    "score": (
                        10
                        if any(
                            keyword in _norm(
                                name + " " + label
                            )
                            for keyword in (
                                "catatan",
                                "perbaikan",
                                "alasan",
                                "keterangan",
                                "note",
                            )
                        )
                        else 1
                    ),
                }
            )

        note_field = ""

        if note_candidates:
            note_field = max(
                note_candidates,
                key=lambda item: item[
                    "score"
                ],
            )[
                "field"
            ]

        decision_map = {}

        for choice in choices:
            decision = choice.get(
                "decision"
            )

            if (
                decision
                and decision
                not in decision_map
            ):
                decision_map[
                    decision
                ] = choice

        text = clean_text(
            form.get_text(
                " ",
                strip=True,
            )
        )

        score = 0

        if method == "POST":
            score += 10

        if action_url:
            score += 2

        score += (
            len(
                decision_map
            )
            * 10
        )

        if note_field:
            score += 4

        if (
            "hasil verifikasi"
            in _norm(text)
        ):
            score += 5

        file_field_names = []

        for file_input in form.find_all(
            "input",
            attrs={
                "type": re.compile(
                    r"^file$",
                    re.I,
                )
            },
        ):
            if file_input.has_attr(
                "disabled"
            ):
                continue

            file_name = (
                file_input.get("name")
                or ""
            ).strip()

            if (
                file_name
                and file_name
                not in file_field_names
            ):
                file_field_names.append(
                    file_name
                )

        hidden_names = []

        for hidden in form.find_all(
            "input",
            attrs={
                "type": "hidden",
            },
        ):
            name = (
                hidden.get("name")
                or ""
            ).strip()

            if name:
                hidden_names.append(
                    name
                )

        return {
            "form_index": form_index,
            "source_page_url": page_url,
            "method": method,
            "action_url": action_url,
            "enctype": enctype,
            "score": score,
            "decision_map": decision_map,
            "note_field": note_field,
            "hidden_field_names": (
                hidden_names
            ),
            "file_field_names": (
                file_field_names
            ),
            "controls": (
                self._form_controls(
                    form
                )
            ),
        }

    def _parse_page(
        self,
        html_text: str,
        *,
        page_url: str,
    ) -> dict:
        soup = BeautifulSoup(
            html_text,
            "lxml",
        )

        forms = []

        for index, form in enumerate(
            soup.find_all(
                "form"
            )
        ):
            forms.append(
                self._parse_form(
                    form,
                    page_url=page_url,
                    form_index=index,
                )
            )

        decision_forms = {}

        for decision in (
            "approve",
            "reject_institution",
            "reject_district",
        ):
            candidates = [
                form
                for form in forms
                if decision
                in form[
                    "decision_map"
                ]
            ]

            if candidates:
                decision_forms[
                    decision
                ] = max(
                    candidates,
                    key=lambda item: item[
                        "score"
                    ],
                )

        csrf_meta = soup.find(
            "meta",
            attrs={
                "name": re.compile(
                    r"csrf",
                    re.I,
                )
            },
        )

        csrf_header_value = ""

        if csrf_meta:
            csrf_header_value = str(
                csrf_meta.get(
                    "content",
                    ""
                )
                or ""
            )

        return {
            "page_url": page_url,
            "forms_count": len(
                forms
            ),
            "forms": forms,
            "decision_forms": (
                decision_forms
            ),
            "csrf_header_value": (
                csrf_header_value
            ),
        }

    def _public_form(
        self,
        form: dict,
        *,
        decision: str,
    ) -> dict:
        choice = (
            form[
                "decision_map"
            ][
                decision
            ]
        )

        hidden_names = (
            form.get(
                "hidden_field_names",
                [],
            )
        )

        return {
            "ready": (
                form.get("method")
                == "POST"
                and bool(
                    form.get(
                        "action_url"
                    )
                )
            ),
            "source_page_url": form.get(
                "source_page_url"
            ),
            "method": form.get(
                "method"
            ),
            "action_url": form.get(
                "action_url"
            ),
            "enctype": form.get(
                "enctype"
            ),
            "decision_control": (
                choice.get(
                    "kind"
                )
            ),
            "decision_field": (
                choice.get(
                    "field"
                )
            ),
            "decision_value": (
                choice.get(
                    "value"
                )
            ),
            "decision_label": (
                choice.get(
                    "label"
                )
            ),
            "decision_source": (
                choice.get(
                    "source",
                    "html_form",
                )
            ),
            "note_field": (
                form.get(
                    "note_field"
                )
            ),
            "file_field_names": list(
                form.get(
                    "file_field_names",
                    [],
                )
            ),
            "hidden_field_names": [
                (
                    name
                    if not _sensitive_field_name(
                        name
                    )
                    else f"{name} [nilai disembunyikan]"
                )
                for name in hidden_names
            ],
        }


    def _inject_verified_district_choice(
        self,
        parsed: dict,
    ) -> dict:
        """
        Inject keputusan Tolak -> Kabupaten hanya bila form saat ini cocok
        dengan schema yang sudah diverifikasi dari Network SIMBA.

        Bukti request nyata yang sudah diamati:
        - POST ke /wilayah/simpan-rekomendasi-wilayah/<aid>/
          diverifikasikabupaten/<provinsi>/<kabupaten|all>/<application_id>
        - field keputusan: terima_tolak
        - approve: terima
        - tolak lembaga: tolak
        - tolak kabupaten: tolak_kabupaten
        - field catatan: catatan_wilayah
        - enctype multipart/form-data

        Fallback ini TIDAK dipakai bila schema form tidak persis cocok.
        """
        if (
            parsed.get("decision_forms", {}).get("reject_district")
        ):
            return parsed

        verified_action_pattern = re.compile(
            r"^/wilayah/simpan-rekomendasi-wilayah/"
            r"[^/]+/diverifikasikabupaten/[^/]+/[^/]+/[^/]+/?$",
            re.I,
        )

        for form in parsed.get("forms", []):
            if form.get("method") != "POST":
                continue

            action_url = str(form.get("action_url") or "")
            action_path = urlparse(action_url).path
            if not verified_action_pattern.match(action_path):
                continue

            decision_map = form.get("decision_map", {})
            approve = decision_map.get("approve") or {}
            reject_inst = decision_map.get("reject_institution") or {}

            if not (
                approve.get("field") == "terima_tolak"
                and str(approve.get("value", "")) == "terima"
                and reject_inst.get("field") == "terima_tolak"
                and str(reject_inst.get("value", "")) == "tolak"
                and form.get("note_field") == "catatan_wilayah"
            ):
                continue

            # Browser capture menunjukkan form menggunakan multipart karena
            # terdapat input file kosong. Terima form tanpa atribut enctype
            # eksplisit hanya bila file field memang ditemukan; selain itu
            # schema dianggap belum cukup kuat untuk fallback LIVE.
            enctype = str(form.get("enctype") or "").lower()
            file_fields = list(form.get("file_field_names") or [])
            if (
                "multipart/form-data" not in enctype
                and not file_fields
            ):
                continue

            district_choice = {
                "kind": "verified_network_capture",
                "field": "terima_tolak",
                "value": "tolak_kabupaten",
                "label": (
                    "Tolak Proposal (Revisi), dan Kembalikan ke Kabupaten"
                ),
                "decision": "reject_district",
                "source": "verified_network_capture",
            }

            decision_map["reject_district"] = district_choice
            parsed.setdefault("decision_forms", {})[
                "reject_district"
            ] = form
            parsed["district_verified_network_fallback"] = True
            return parsed

        parsed["district_verified_network_fallback"] = False
        return parsed

    def _related_decision_urls(
        self,
        html_text: str,
        *,
        page_url: str,
    ) -> list[str]:
        # GET-only discovery of same-origin pages related to verification.
        soup = BeautifulSoup(html_text, "lxml")
        base = urlparse(page_url)
        candidates = []

        def add(value: str) -> None:
            raw = str(value or "").strip()
            if not raw or raw.startswith(("javascript:", "#", "mailto:")):
                return
            url = urljoin(page_url, raw)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
                return
            low = url.lower()
            if any(ext in low for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".pdf")):
                return
            if not any(word in low for word in ("verifikasi", "rekomendasi", "kabupaten", "tolak", "wilayah")):
                return
            if url == page_url or url in candidates:
                return
            candidates.append(url)

        for tag in soup.find_all(True):
            for attr in ("href", "data-url", "data-href", "data-action", "formaction"):
                add(tag.get(attr, ""))
            onclick = str(tag.get("onclick", "") or "")
            for match in re.findall(r"[\"']([^\"']+)[\"']", onclick):
                add(match)

        for script in soup.find_all("script"):
            body = str(script.string or script.get_text(" ", strip=False) or "")
            pattern = r"[\"'](/[^\"']*(?:verifikasi|rekomendasi|kabupaten|tolak|wilayah)[^\"']*)[\"']"
            for match in re.findall(pattern, body, flags=re.I):
                add(match)

        return candidates[:12]

    def _discover_reject_district(
        self,
        html_text: str,
        *,
        page_url: str,
    ) -> tuple[dict | None, dict | None, list[str]]:
        checked = []
        for candidate in self._related_decision_urls(html_text, page_url=page_url):
            try:
                candidate_html, final_url = self.client.get_html(candidate)
            except Exception:
                continue
            if final_url in checked:
                continue
            checked.append(final_url)
            parsed = self._parse_page(candidate_html, page_url=final_url)
            form = parsed.get("decision_forms", {}).get("reject_district")
            if form:
                return form, parsed, checked
        return None, None, checked

    def _merge_for_route_validation(
        self,
        primary: dict,
        extra: dict | None,
    ) -> dict:
        if not extra:
            return primary
        merged = dict(primary)
        merged_forms = list(primary.get("forms", [])) + list(extra.get("forms", []))
        merged_decisions = dict(primary.get("decision_forms", {}))
        merged_decisions.update(extra.get("decision_forms", {}))
        merged["forms"] = merged_forms
        merged["forms_count"] = len(merged_forms)
        merged["decision_forms"] = merged_decisions
        return merged

    def _decision_fingerprint(
        self,
        form: dict,
        *,
        decision: str,
    ) -> tuple:
        choice = (
            form.get(
                "decision_map",
                {}
            ).get(
                decision,
                {}
            )
        )

        return (
            form.get(
                "method"
            ),
            form.get(
                "action_url"
            ),
            choice.get(
                "kind"
            ),
            choice.get(
                "field"
            ),
            str(
                choice.get(
                    "value",
                    ""
                )
            ),
        )

    def _validate_reject_routes(
        self,
        parsed: dict,
    ) -> dict:
        """
        Pastikan Tolak ke Lembaga dan Tolak ke Kabupaten benar-benar
        merupakan kontrol/form yang berbeda.

        Bila fingerprint identik, live reject diblokir karena kita tidak
        dapat membuktikan tujuan pengembalian.
        """
        institution_form = (
            parsed.get(
                "decision_forms",
                {}
            ).get(
                "reject_institution"
            )
        )

        district_form = (
            parsed.get(
                "decision_forms",
                {}
            ).get(
                "reject_district"
            )
        )

        if not institution_form:
            return {
                "safe": False,
                "error": (
                    "Kontrol 'Tolak ke Lembaga' tidak ditemukan."
                ),
            }

        if not district_form:
            return {
                "safe": False,
                "error": (
                    "Kontrol 'Tolak ke Kabupaten' tidak ditemukan."
                ),
            }

        institution_fp = (
            self._decision_fingerprint(
                institution_form,
                decision="reject_institution",
            )
        )

        district_fp = (
            self._decision_fingerprint(
                district_form,
                decision="reject_district",
            )
        )

        if (
            institution_fp
            == district_fp
        ):
            return {
                "safe": False,
                "error": (
                    "Kontrol penolakan ke Lembaga dan ke Kabupaten "
                    "terdeteksi identik. LIVE reject diblokir agar tujuan "
                    "pengembalian tidak tertukar."
                ),
                "institution_fingerprint": institution_fp,
                "district_fingerprint": district_fp,
            }

        return {
            "safe": True,
            "institution_fingerprint": institution_fp,
            "district_fingerprint": district_fp,
        }

    def _diagnostic_controls(
        self,
        parsed: dict,
    ) -> list[dict]:
        output = []

        for form in parsed.get(
            "forms",
            []
        ):
            for decision, choice in (
                form.get(
                    "decision_map",
                    {}
                ).items()
            ):
                output.append(
                    {
                        "form_index": form.get(
                            "form_index"
                        ),
                        "method": form.get(
                            "method"
                        ),
                        "action_url": form.get(
                            "action_url"
                        ),
                        "decision": decision,
                        "control": choice.get(
                            "kind"
                        ),
                        "field": choice.get(
                            "field"
                        ),
                        "value": choice.get(
                            "value"
                        ),
                        "label": choice.get(
                            "label"
                        ),
                    }
                )

        return output

    def inspect_verification_page(
        self,
        verification_url: str,
    ) -> dict:
        if not verification_url:
            return {
                "ready": False,
                "error": (
                    "URL Hasil Verifikasi tidak ditemukan."
                ),
                "decisions": {},
            }

        html_text, final_url = (
            self.client.get_html(
                verification_url
            )
        )

        parsed = self._parse_page(
            html_text,
            page_url=final_url,
        )
        parsed = self._inject_verified_district_choice(
            parsed
        )
        district_checked_urls = []
        if not parsed.get("decision_forms", {}).get("reject_district"):
            district_form, district_extra_parsed, district_checked_urls = self._discover_reject_district(
                html_text,
                page_url=final_url,
            )
            if district_form and district_extra_parsed:
                parsed = self._merge_for_route_validation(parsed, district_extra_parsed)

        decisions = {}

        reject_route_validation = (
            self._validate_reject_routes(
                parsed
            )
        )

        for decision in (
            "approve",
            "reject_institution",
            "reject_district",
        ):
            form = (
                parsed[
                    "decision_forms"
                ].get(
                    decision
                )
            )

            if not form:
                decisions[
                    decision
                ] = {
                    "ready": False,
                    "error": (
                        "Pilihan keputusan tidak ditemukan "
                        "pada form HTML."
                    ),
                }
                continue

            public = (
                self._public_form(
                    form,
                    decision=decision,
                )
            )

            # Tolak -> Lembaga sudah punya kontrol eksplisit dari SIMBA:
            # terima_tolak=tolak dengan label "Kembalikan ke Lembaga".
            # Jadi jalur ini boleh LIVE walaupun kontrol Kabupaten tidak ada.
            #
            # Tolak -> Kabupaten boleh LIVE bila kontrol HTML asli ada
            # ATAU schema form cocok dengan request Network yang sudah
            # diverifikasi (terima_tolak=tolak_kabupaten).
            if (
                decision
                == "reject_district"
                and not reject_route_validation.get(
                    "safe",
                    False,
                )
            ):
                public[
                    "ready"
                ] = False
                public[
                    "error"
                ] = (
                    reject_route_validation.get(
                        "error"
                    )
                    or "Kontrol Tolak ke Kabupaten belum ditemukan."
                )

            if (
                decision
                in {
                    "reject_institution",
                    "reject_district",
                }
                and not public.get(
                    "note_field"
                )
            ):
                public[
                    "ready"
                ] = False
                public[
                    "error"
                ] = (
                    "Field catatan penolakan tidak ditemukan."
                )

            decisions[
                decision
            ] = public

        return {
            "ready": all(
                item.get(
                    "ready",
                    False,
                )
                for item
                in decisions.values()
            ),
            "page_url": final_url,
            "forms_count": (
                parsed[
                    "forms_count"
                ]
            ),
            "decisions": decisions,
            "reject_route_validation": (
                reject_route_validation
            ),
            "diagnostic_controls": (
                self._diagnostic_controls(
                    parsed
                )
            ),
            "district_discovery_checked_urls": district_checked_urls,
            "district_discovery_found": bool(parsed.get("decision_forms", {}).get("reject_district")),
            "district_verified_network_fallback": bool(
                parsed.get(
                    "district_verified_network_fallback",
                    False,
                )
            ),
        }

    def _fresh_form_for_decision(
        self,
        verification_url: str,
        decision: str,
    ) -> tuple[dict, dict]:
        html_text, final_url = (
            self.client.get_html(
                verification_url
            )
        )

        primary_parsed = self._parse_page(
            html_text,
            page_url=final_url,
        )
        primary_parsed = self._inject_verified_district_choice(
            primary_parsed
        )
        parsed = primary_parsed
        form = parsed["decision_forms"].get(decision)
        validation_parsed = primary_parsed

        if decision == "reject_district" and not form:
            district_form, district_parsed, _checked = self._discover_reject_district(
                html_text,
                page_url=final_url,
            )
            if district_form and district_parsed:
                form = district_form
                parsed = district_parsed
                validation_parsed = self._merge_for_route_validation(primary_parsed, district_parsed)

        # Hanya Tolak -> Kabupaten yang membutuhkan bukti adanya
        # kontrol Kabupaten yang berbeda. Tolak -> Lembaga sudah
        # memiliki kontrol eksplisit sendiri pada form SIMBA.
        if (
            decision
            == "reject_district"
        ):
            reject_route_validation = (
                self._validate_reject_routes(
                    validation_parsed
                )
            )

            if not reject_route_validation.get(
                "safe",
                False,
            ):
                raise LiveVerificationError(
                    reject_route_validation.get(
                        "error"
                    )
                    or "Kontrol Tolak ke Kabupaten belum ditemukan. "
                       "LIVE Kabupaten diblokir."
                )

        if not form:
            raise LiveVerificationError(
                "Form untuk keputusan yang dipilih "
                "tidak ditemukan pada halaman SIMBA."
            )

        if form.get(
            "method"
        ) != "POST":
            raise LiveVerificationError(
                "Form SIMBA yang terdeteksi bukan POST. "
                "Pengiriman diblokir."
            )

        if not form.get(
            "action_url"
        ):
            raise LiveVerificationError(
                "Action URL form tidak ditemukan. "
                "Pengiriman diblokir."
            )

        if (
            decision
            in {
                "reject_institution",
                "reject_district",
            }
            and not form.get(
                "note_field"
            )
        ):
            raise LiveVerificationError(
                "Field catatan penolakan tidak ditemukan. "
                "Pengiriman diblokir."
            )

        return (
            form,
            parsed,
        )

    def _payload_for_decision(
        self,
        form: dict,
        *,
        decision: str,
        note: str,
    ) -> list[tuple[str, str]]:
        choice = (
            form[
                "decision_map"
            ].get(
                decision
            )
        )

        if not choice:
            raise LiveVerificationError(
                "Nilai keputusan pada form SIMBA tidak ditemukan."
            )

        controls = list(
            form.get(
                "controls",
                []
            )
        )

        decision_field = (
            choice.get(
                "field"
            )
            or ""
        )

        if not decision_field:
            raise LiveVerificationError(
                "Nama field keputusan kosong."
            )

        # Hapus nilai default untuk field keputusan.
        controls = [
            pair
            for pair in controls
            if pair[0]
            != decision_field
        ]

        controls.append(
            (
                decision_field,
                str(
                    choice.get(
                        "value",
                        ""
                    )
                ),
            )
        )

        note_field = (
            form.get(
                "note_field"
            )
            or ""
        )

        if note_field:
            controls = [
                pair
                for pair in controls
                if pair[0]
                != note_field
            ]

            controls.append(
                (
                    note_field,
                    note or "",
                )
            )

        return controls

    def submit_once(
        self,
        *,
        verification_url: str,
        institution,
        decision: str,
        note: str = "",
    ) -> dict:
        if decision not in self.EXPECTED_STATUS:
            raise LiveVerificationError(
                "Keputusan verifikasi tidak dikenali."
            )

        if (
            decision
            in {
                "reject_institution",
                "reject_district",
            }
            and not (
                note
                or ""
            ).strip()
        ):
            raise LiveVerificationError(
                "Catatan wajib diisi untuk penolakan."
            )

        existing = (
            self.submission_log.get(
                institution.application_id
            )
        )

        if (
            existing
            and existing.get(
                "state"
            )
            in {
                "SENT_UNCONFIRMED",
                "CONFIRMED",
            }
        ):
            raise LiveVerificationError(
                "Pengajuan ini sudah pernah dikirim dari aplikasi. "
                "POST ulang diblokir untuk mencegah pengiriman ganda. "
                "Periksa SIMBA terlebih dahulu."
            )

        # Validasi target sebelum GET form terakhir.
        snapshot = (
            self.client.read_target_snapshot(
                institution=institution
            )
        )

        if not snapshot.get(
            "safe_identity"
        ):
            raise LiveVerificationError(
                "Identitas target tidak cocok. "
                "POST diblokir."
            )

        form, parsed = (
            self._fresh_form_for_decision(
                verification_url,
                decision,
            )
        )

        payload = (
            self._payload_for_decision(
                form,
                decision=decision,
                note=note,
            )
        )

        headers = {
            "Referer": (
                parsed.get(
                    "page_url"
                )
                or verification_url
            ),
            "Origin": (
                self.client.base_url
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,"
                "application/json;q=0.8,*/*;q=0.7"
            ),
        }

        csrf_value = (
            parsed.get(
                "csrf_header_value"
            )
            or ""
        )

        if csrf_value:
            headers[
                "X-CSRF-TOKEN"
            ] = csrf_value

        enctype = (
            form.get(
                "enctype"
            )
            or ""
        ).lower()

        self.submission_log.record(
            institution.application_id,
            decision=decision,
            state="SENDING",
        )

        try:
            if (
                "multipart/form-data"
                in enctype
            ):
                multipart_fields = [
                    (
                        name,
                        (
                            None,
                            value,
                        ),
                    )
                    for name, value
                    in payload
                ]

                # Browser SIMBA mengirim input file kosong sebagai part
                # multipart (contoh: path_rekomendasi_wilayah dan files).
                # Kita meniru struktur itu tanpa mengunggah file apa pun.
                for file_field in form.get(
                    "file_field_names",
                    [],
                ):
                    multipart_fields.append(
                        (
                            file_field,
                            (
                                "",
                                b"",
                                "application/octet-stream",
                            ),
                        )
                    )

                response = (
                    self.client.session.post(
                        form[
                            "action_url"
                        ],
                        files=multipart_fields,
                        headers=headers,
                        timeout=60,
                        allow_redirects=True,
                    )
                )

                if response.status_code >= 400:
                    raise LiveVerificationError(
                        f"HTTP {response.status_code} saat POST verifikasi."
                    )

                if "/login" in response.url.lower():
                    raise LiveVerificationError(
                        "POST diarahkan ke login. "
                        "Session SIMBA kemungkinan kedaluwarsa."
                    )

            else:
                response = (
                    self.client._request(
                        "POST",
                        form[
                            "action_url"
                        ],
                        data=payload,
                        headers=headers,
                        timeout=60,
                    )
                )

        except Exception as exc:
            self.submission_log.record(
                institution.application_id,
                decision=decision,
                state="SEND_FAILED",
                result={
                    "error": str(
                        exc
                    )
                },
            )

            if isinstance(
                exc,
                LiveVerificationError,
            ):
                raise

            raise LiveVerificationError(
                f"POST verifikasi gagal: {exc}"
            ) from exc

        result = {
            "post_performed": True,
            "decision": decision,
            "expected_status": (
                self.EXPECTED_STATUS[
                    decision
                ]
            ),
            "response_status_code": (
                response.status_code
            ),
            "response_final_url": (
                response.url
            ),
            "response_text": (
                response.text[:8000]
            ),
            "form_action_url": (
                form[
                    "action_url"
                ]
            ),
            "form_method": "POST",
            "decision_field": (
                form[
                    "decision_map"
                ][
                    decision
                ].get(
                    "field"
                )
            ),
            "decision_value": (
                form[
                    "decision_map"
                ][
                    decision
                ].get(
                    "value"
                )
            ),
            "decision_label": (
                form[
                    "decision_map"
                ][
                    decision
                ].get(
                    "label"
                )
            ),
            "decision_fingerprint": (
                self._decision_fingerprint(
                    form,
                    decision=decision,
                )
            ),
            "note_field": (
                form.get(
                    "note_field"
                )
            ),
        }

        self.submission_log.record(
            institution.application_id,
            decision=decision,
            state="SENT_UNCONFIRMED",
            response_status_code=(
                response.status_code
            ),
            result={
                "expected_status": (
                    result[
                        "expected_status"
                    ]
                ),
                "response_final_url": (
                    response.url
                ),
            },
        )

        return result

    def _record_from_payload(
        self,
        payload: dict,
        application_id: str,
    ) -> tuple[bool, dict]:
        """
        Ambil record proposal yang sama dari DataTables setelah POST.

        Kita sengaja mengembalikan beberapa field bukti agar verifikasi
        tidak hanya bergantung pada HTTP 200 / status saja.
        """
        rows = payload.get(
            "data",
            [],
        )

        if not isinstance(
            rows,
            list,
        ):
            return (
                False,
                {},
            )

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                continue

            if str(
                row.get(
                    "id",
                    ""
                )
            ) != str(
                application_id
            ):
                continue

            return (
                True,
                {
                    "id": str(
                        row.get(
                            "id",
                            ""
                        )
                    ),
                    "status": clean_text(
                        row.get(
                            "status"
                        )
                    ),
                    "catatan": clean_text(
                        row.get(
                            "catatan"
                        )
                    ),
                    "catatan_kabupaten": clean_text(
                        row.get(
                            "catatan_kabupaten"
                        )
                    ),
                    "catatan_wilayah": clean_text(
                        row.get(
                            "catatan_wilayah"
                        )
                    ),
                    "options": str(
                        row.get(
                            "options",
                            ""
                        )
                        or ""
                    ),
                    "nspp": clean_text(
                        row.get(
                            "nspp"
                        )
                    ),
                    "pesantren": clean_text(
                        row.get(
                            "pesantren"
                        )
                    ),
                    "updated_at": clean_text(
                        row.get(
                            "updated_at"
                        )
                    ),
                },
            )

        return (
            False,
            {},
        )

    def _contains_phrase(
        self,
        value: str,
        phrase: str,
    ) -> bool:
        return (
            _norm(
                phrase
            )
            in _norm(
                value
            )
        )

    def _status_matches_decision(
        self,
        value: str,
        decision: str,
    ) -> bool:
        """
        Cocokkan status SIMBA terhadap keputusan.

        Bukti hasil nyata Tolak -> Kabupaten:
        "Ditolak kanwil ke kabupaten".

        Status generic "Ditolak Kanwil" tetap dapat menjadi bukti bahwa
        proposal sudah ditolak, tetapi tujuan Lembaga/Kabupaten tetap
        harus dikonfirmasi lewat destination evidence.
        """
        normalized_value = _norm(
            value
        )

        if not normalized_value:
            return False

        variants = (
            self.EXPECTED_STATUS_VARIANTS.get(
                decision,
                (
                    self.EXPECTED_STATUS.get(
                        decision,
                        ""
                    ),
                ),
            )
        )

        return any(
            _norm(variant)
            in normalized_value
            for variant in variants
            if variant
        )

    def _reject_destination_evidence(
        self,
        *,
        decision: str,
        response_text: str,
        detail_text: str,
        queue_record: dict,
    ) -> dict:
        """
        Validasi tujuan pengembalian setelah POST.

        Data nyata SIMBA yang sudah diamati:
        - Tolak -> Lembaga dapat meninggalkan label
          "Catatan kanwil ke lembaga".
        - Tolak -> Kabupaten meninggalkan status
          "Ditolak kanwil ke kabupaten" dan label
          "Catatan kanwil ke kabupaten".
        """
        if decision not in {
            "reject_institution",
            "reject_district",
        }:
            return {
                "required": False,
                "confirmed": True,
                "destination": "",
                "matched_phrase": "",
                "source": "",
            }

        if decision == "reject_institution":
            destination = "Lembaga"
            phrases = [
                "catatan kanwil ke lembaga",
                "kanwil ke lembaga",
            ]
        else:
            destination = "Kabupaten"
            phrases = [
                "catatan kanwil ke kabupaten",
                "kanwil ke kabupaten",
            ]

        sources = {
            "response": response_text or "",
            "detail": detail_text or "",
            "queue.status": queue_record.get(
                "status",
                ""
            ),
            "queue.catatan": queue_record.get(
                "catatan",
                ""
            ),
            "queue.catatan_kabupaten": queue_record.get(
                "catatan_kabupaten",
                ""
            ),
            "queue.catatan_wilayah": queue_record.get(
                "catatan_wilayah",
                ""
            ),
        }

        for source_name, source_value in sources.items():
            for phrase in phrases:
                if self._contains_phrase(
                    source_value,
                    phrase,
                ):
                    return {
                        "required": True,
                        "confirmed": True,
                        "destination": destination,
                        "matched_phrase": phrase,
                        "source": source_name,
                    }

        return {
            "required": True,
            "confirmed": False,
            "destination": destination,
            "matched_phrase": "",
            "source": "",
        }

    def _note_saved_evidence(
        self,
        *,
        expected_note: str,
        queue_record: dict,
        response_text: str,
        detail_text: str,
    ) -> dict:
        expected = _norm(
            expected_note
        )

        if not expected:
            return {
                "required": False,
                "confirmed": True,
                "source": "",
            }

        sources = {
            "queue.catatan": queue_record.get(
                "catatan",
                ""
            ),
            "queue.catatan_kabupaten": queue_record.get(
                "catatan_kabupaten",
                ""
            ),
            "queue.catatan_wilayah": queue_record.get(
                "catatan_wilayah",
                ""
            ),
            "response": response_text or "",
            "detail": detail_text or "",
        }

        # Cocok persis setelah normalisasi.
        for source_name, source_value in sources.items():
            normalized_source = _norm(
                source_value
            )

            if (
                expected
                and expected
                in normalized_source
            ):
                return {
                    "required": True,
                    "confirmed": True,
                    "source": source_name,
                }

        # Fallback: gunakan token bermakna untuk catatan panjang.
        expected_tokens = {
            token
            for token in re.findall(
                r"[a-z0-9]+",
                expected,
            )
            if len(
                token
            ) >= 4
        }

        if expected_tokens:
            for source_name, source_value in sources.items():
                source_tokens = set(
                    re.findall(
                        r"[a-z0-9]+",
                        _norm(
                            source_value
                        ),
                    )
                )

                matched = (
                    expected_tokens
                    & source_tokens
                )

                ratio = (
                    len(
                        matched
                    )
                    / len(
                        expected_tokens
                    )
                )

                if ratio >= 0.75:
                    return {
                        "required": True,
                        "confirmed": True,
                        "source": source_name,
                        "token_match_ratio": round(
                            ratio,
                            3,
                        ),
                    }

        return {
            "required": True,
            "confirmed": False,
            "source": "",
        }

    def _derive_processed_ajax_url(
        self,
        *,
        institution_ajax_url: str,
        detail_url: str,
    ) -> str:
        """
        Bentuk endpoint GET hasil Kanwil.

        Prioritas:
        1. Jika AJAX daftar awal memakai /diverifikasikabupaten/data-index/,
           ganti menjadi /diproseskanwil/data-index/ dan pertahankan query.
        2. Jika tidak, bentuk dari route detail proposal.

        Tidak ada POST di fungsi ini.
        """
        source = (
            institution_ajax_url
            or ""
        ).strip()

        if (
            source
            and "/diverifikasikabupaten/data-index/"
            in source
        ):
            return source.replace(
                "/diverifikasikabupaten/data-index/",
                "/diproseskanwil/data-index/",
                1,
            )

        match = re.search(
            r"/wilayah/verifikasi/([^/]+)/"
            r"(?:diverifikasikabupaten|diproseskanwil)/"
            r"([^/]+)/([^/]+)/([^/]+)/show/",
            detail_url or "",
            flags=re.IGNORECASE,
        )

        if not match:
            return ""

        aid_id, province_id, district_id, _application_id = (
            match.groups()
        )

        return self.client.make_url(
            "/wilayah/verifikasi/"
            f"{aid_id}/diproseskanwil/data-index/"
            f"{province_id}/{district_id}"
        )

    def _query_processed_record(
        self,
        *,
        institution,
        institution_ajax_url: str,
        institution_method: str,
        institution_page_size: int,
        institution_extra_params: Optional[dict],
    ) -> dict:
        """
        GET endpoint diproseskanwil/data-index dan cari application_id
        yang sama. Gunakan global search NSPP agar hasil kecil.
        """
        processed_url = (
            self._derive_processed_ajax_url(
                institution_ajax_url=(
                    institution_ajax_url
                ),
                detail_url=(
                    institution.detail_url
                ),
            )
        )

        if not processed_url:
            return {
                "url": "",
                "found": False,
                "record": {},
                "error": (
                    "Endpoint hasil Kanwil tidak dapat dibentuk."
                ),
            }

        extra_params = dict(
            institution_extra_params
            or {}
        )

        # Override global search dengan NSPP target.
        extra_params[
            "search[value]"
        ] = (
            institution.nspp
            or institution.name
            or institution.application_id
        )
        extra_params[
            "search[regex]"
        ] = "false"

        try:
            payload, final_url = (
                self.client.request_datatable(
                    processed_url,
                    method="GET",
                    page_size=max(
                        25,
                        min(
                            int(
                                institution_page_size
                            ),
                            500,
                        ),
                    ),
                    extra_params=extra_params,
                )
            )

            found, record = (
                self._record_from_payload(
                    payload,
                    institution.application_id,
                )
            )

            return {
                "url": final_url,
                "found": found,
                "record": record,
                "error": "",
            }

        except Exception as exc:
            return {
                "url": processed_url,
                "found": False,
                "record": {},
                "error": str(
                    exc
                ),
            }

    def verify_after_submit(
        self,
        *,
        institution,
        decision: str,
        submit_result: dict,
        institution_ajax_url: str = "",
        institution_method: str = "GET",
        institution_page_size: int = 500,
        institution_extra_params: Optional[dict] = None,
        expected_note: str = "",
    ) -> dict:
        """
        Verifikasi pasca-POST tiga lapis:

        1. Identitas proposal tetap sama.
        2. Status akhir sesuai keputusan.
        3. Untuk reject, tujuan Lembaga/Kabupaten dibuktikan secara eksplisit
           bila SIMBA menyediakannya.

        Catatan:
        - Tolak -> Kabupaten sekarang memiliki bukti hasil nyata:
          "Ditolak kanwil ke kabupaten" dan
          "Catatan kanwil ke kabupaten".
        - Status generic "Ditolak Kanwil" tetap belum cukup untuk
          membedakan tujuan.
        - Jika status reject ada tetapi bukti tujuan belum ditemukan,
          hasil menjadi STATUS_CONFIRMED_DESTINATION_UNCONFIRMED.
        """
        expected_status = (
            self.EXPECTED_STATUS[
                decision
            ]
        )

        response_text = clean_text(
            submit_result.get(
                "response_text",
                ""
            )
        )

        response_contains_expected = (
            self._status_matches_decision(
                response_text,
                decision,
            )
        )

        response_contains_old = (
            self.OLD_STATUS.lower()
            in response_text.lower()
        )

        detail_contains_expected = False
        detail_final_url = ""
        detail_text = ""

        # GET-only fallback. Aman karena tidak mengubah data.
        detail_candidates = [
            institution.detail_url,
        ]

        if (
            "diverifikasikabupaten"
            in (
                institution.detail_url
                or ""
            )
        ):
            detail_candidates.append(
                institution.detail_url.replace(
                    "diverifikasikabupaten",
                    "diproseskanwil",
                )
            )

        for detail_url in detail_candidates:
            if not detail_url:
                continue

            try:
                html_text, final_url = (
                    self.client.get_html(
                        detail_url
                    )
                )

                detail_final_url = (
                    final_url
                )

                detail_text = clean_text(
                    BeautifulSoup(
                        html_text,
                        "lxml",
                    ).get_text(
                        " ",
                        strip=True,
                    )
                )

                if self._status_matches_decision(
                    detail_text,
                    decision,
                ):
                    detail_contains_expected = True

                # Jangan break; route processed dapat memberi bukti
                # yang lebih lengkap daripada route lama.
                if (
                    "/diproseskanwil/"
                    in final_url
                ):
                    break

            except Exception:
                continue

        queue_record_found = False
        queue_record = {}
        queue_status = ""
        queue_expected = False
        queue_old = False
        queue_identity_match = False

        # Setelah POST, proposal biasanya berpindah dari daftar
        # diverifikasikabupaten ke diproseskanwil. Karena itu verifikasi
        # utama dilakukan dengan GET ke endpoint hasil Kanwil.
        processed_result = (
            self._query_processed_record(
                institution=institution,
                institution_ajax_url=(
                    institution_ajax_url
                ),
                institution_method=(
                    institution_method
                ),
                institution_page_size=(
                    institution_page_size
                ),
                institution_extra_params=(
                    institution_extra_params
                ),
            )
        )

        queue_record_found = (
            processed_result.get(
                "found",
                False,
            )
        )
        queue_record = (
            processed_result.get(
                "record",
                {}
            )
            or {}
        )

        queue_status = (
            queue_record.get(
                "status",
                ""
            )
        )

        queue_expected = (
            queue_record_found
            and self._status_matches_decision(
                queue_status,
                decision,
            )
        )

        queue_old = (
            queue_record_found
            and queue_status.lower()
            == self.OLD_STATUS.lower()
        )

        queue_identity_match = (
            queue_record_found
            and (
                not institution.nspp
                or queue_record.get(
                    "nspp",
                    ""
                )
                == institution.nspp
            )
            and (
                not institution.name
                or _norm(
                    queue_record.get(
                        "pesantren",
                        ""
                    )
                )
                == _norm(
                    institution.name
                )
            )
        )

        # Fallback ke endpoint lama hanya bila record hasil Kanwil belum
        # ditemukan. Ini GET-only dan tidak mengubah data.
        if (
            not queue_record_found
            and institution_ajax_url
        ):
            try:
                payload, _ = (
                    self.client.request_datatable(
                        institution_ajax_url,
                        method=(
                            institution_method
                        ),
                        page_size=int(
                            institution_page_size
                        ),
                        extra_params=(
                            institution_extra_params
                            or {}
                        ),
                    )
                )

                (
                    fallback_found,
                    fallback_record,
                ) = (
                    self._record_from_payload(
                        payload,
                        institution.application_id,
                    )
                )

                if fallback_found:
                    queue_record_found = True
                    queue_record = (
                        fallback_record
                    )
                    queue_status = (
                        queue_record.get(
                            "status",
                            ""
                        )
                    )
                    queue_expected = (
                        self._status_matches_decision(
                            queue_status,
                            decision,
                        )
                    )
                    queue_old = (
                        queue_status.lower()
                        == self.OLD_STATUS.lower()
                    )
                    queue_identity_match = (
                        (
                            not institution.nspp
                            or queue_record.get(
                                "nspp",
                                ""
                            )
                            == institution.nspp
                        )
                        and (
                            not institution.name
                            or _norm(
                                queue_record.get(
                                    "pesantren",
                                    ""
                                )
                            )
                            == _norm(
                                institution.name
                            )
                        )
                    )

            except Exception:
                pass

        status_confirmed = (
            response_contains_expected
            or detail_contains_expected
            or queue_expected
        )

        destination_evidence = (
            self._reject_destination_evidence(
                decision=decision,
                response_text=response_text,
                detail_text=detail_text,
                queue_record=queue_record,
            )
        )

        note_evidence = (
            self._note_saved_evidence(
                expected_note=expected_note,
                queue_record=queue_record,
                response_text=response_text,
                detail_text=detail_text,
            )
        )

        if decision == "approve":
            fully_confirmed = (
                status_confirmed
                and (
                    not queue_record_found
                    or queue_identity_match
                )
            )

        else:
            fully_confirmed = (
                status_confirmed
                and destination_evidence.get(
                    "confirmed",
                    False,
                )
                and (
                    not queue_record_found
                    or queue_identity_match
                )
            )

        if fully_confirmed:
            result_code = "CONFIRMED"
            state = "CONFIRMED"

        elif (
            decision
            in {
                "reject_institution",
                "reject_district",
            }
            and status_confirmed
            and not destination_evidence.get(
                "confirmed",
                False,
            )
        ):
            result_code = (
                "STATUS_CONFIRMED_DESTINATION_UNCONFIRMED"
            )
            state = "SENT_UNCONFIRMED"

        elif queue_old:
            result_code = "STILL_OLD_STATUS"
            state = "SENT_UNCONFIRMED"

        else:
            result_code = "UNCONFIRMED"
            state = "SENT_UNCONFIRMED"

        evidence = {
            "expected_status": expected_status,
            "response_status_code": (
                submit_result.get(
                    "response_status_code"
                )
            ),
            "response_final_url": (
                submit_result.get(
                    "response_final_url"
                )
            ),
            "response_contains_expected_status": (
                response_contains_expected
            ),
            "response_contains_old_status": (
                response_contains_old
            ),
            "detail_contains_expected_status": (
                detail_contains_expected
            ),
            "detail_final_url": (
                detail_final_url
            ),
            "old_detail_route_became_invalid": (
                bool(
                    institution.detail_url
                )
                and "/diverifikasikabupaten/"
                in institution.detail_url
                and bool(
                    detail_final_url
                )
                and "/diproseskanwil/"
                in detail_final_url
            ),
            "processed_ajax_url": (
                processed_result.get(
                    "url",
                    ""
                )
            ),
            "processed_ajax_error": (
                processed_result.get(
                    "error",
                    ""
                )
            ),
            "queue_record_found": (
                queue_record_found
            ),
            "queue_identity_match": (
                queue_identity_match
            ),
            "queue_status": (
                queue_status
            ),
            "queue_expected_status": (
                queue_expected
            ),
            "queue_old_status": (
                queue_old
            ),
            "queue_catatan": (
                queue_record.get(
                    "catatan",
                    ""
                )
            ),
            "queue_catatan_kabupaten": (
                queue_record.get(
                    "catatan_kabupaten",
                    ""
                )
            ),
            "queue_catatan_wilayah": (
                queue_record.get(
                    "catatan_wilayah",
                    ""
                )
            ),
            "queue_updated_at": (
                queue_record.get(
                    "updated_at",
                    ""
                )
            ),
            "status_confirmed": (
                status_confirmed
            ),
            "destination_evidence": (
                destination_evidence
            ),
            "note_evidence": (
                note_evidence
            ),
            "confirmed": (
                fully_confirmed
            ),
            "result": (
                result_code
            ),
        }

        self.submission_log.record(
            institution.application_id,
            decision=decision,
            state=state,
            response_status_code=(
                submit_result.get(
                    "response_status_code"
                )
            ),
            result=evidence,
        )

        return evidence
