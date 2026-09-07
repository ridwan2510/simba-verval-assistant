from services.checklist_service import (
    get_rules_for_document,
)

title, rules = get_rules_for_document(
    "Surat Keputusan Kepengurusan yang sah dan masih berlaku"
)

assert title == "Surat Keputusan Kepengurusan"
assert any(
    "konsideran" in rule.lower()
    and "menimbang" in rule.lower()
    for rule in rules
)
assert any(
    "diktum" in rule.lower()
    and "memutuskan" in rule.lower()
    for rule in rules
)
assert any(
    "daftar/susunan pengurus" in rule.lower()
    for rule in rules
)

print("V7.3 SK CHECKLIST OK")
