"""Translation validator: what a machine translation may and may not change.

The acronym rule follows the existing zh memory: technical terms stay in Latin
letters (ESC, GCS, EKF), and the glossary is the explicit escape hatch when a
term has an established Chinese form (RTL -> 返航).
"""

from __future__ import annotations

from tools.translate import Validator, allowed_numbers


def test_validator_keeps_an_acronym_with_its_glossary_identity():
    validator = Validator({"ESC": "ESC"})
    assert validator.problems("ESC mask", "ESC 掩码") == []


def test_validator_rejects_a_translated_acronym_without_a_glossary_entry():
    validator = Validator({})
    assert validator.problems("ESC mask", "电调掩码") == ["acronym ESC dropped"]


def test_validator_allows_a_glossary_term_to_replace_an_acronym():
    validator = Validator({"RTL": "返航"})
    assert validator.problems("RTL altitude", "返航高度") == []


def test_validator_allows_zero_to_become_a_digit():
    validator = Validator({})
    assert validator.problems("Set to zero", "设为 0") == []
    assert allowed_numbers("Set to zero") == ["0"]


def test_validator_rejects_a_number_the_source_does_not_have():
    validator = Validator({})
    assert validator.problems("Set to zero", "设为 1") == ["number 1 invented"]


def test_validator_allows_a_month_name_to_become_its_number():
    validator = Validator({})
    assert validator.problems("February 2026", "2026 年 2 月") == []


def test_validator_allows_ordinal_and_multiplier_words_to_become_digits():
    validator = Validator({})
    assert validator.problems("Fourth button Pin", "4番目のボタンピン") == []
    assert validator.problems("SeventhIMU", "7番目のIMU") == []
    assert validator.problems("triple loop-rate", "3重ループレート") == []
    assert validator.problems("twice as fast", "2倍速い") == []
    assert validator.problems("WheelEncoder 2 counts per revolution", "1回転あたり2カウント") == []
    assert validator.problems("octal 1200 (hex 0x280, decimal 640)", "8進数1200（16進数0x280、10進数640）") == []
    assert validator.problems("0 is linear, 1 is cubic", "0은 선형, 1은 3차") == []
