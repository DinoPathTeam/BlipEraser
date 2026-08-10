"""Tests para utils/confirm.py (plan de confirmación, sin PyQt6).

Cubre lo pedido: el umbral de gran tamaño (5 GiB) y que la confirmación
destructiva nunca se pueda saltar (no hay opción de "no volver a preguntar"
ni en el plan ni en las claves i18n).
"""

from blip_eraser.utils.confirm import (
    ALWAYS_CONFIRM_DESTRUCTIVE,
    LARGE_DELETE_THRESHOLD_BYTES,
    ConfirmItem,
    build_category_summary,
    build_confirmation_plan,
    is_large_operation,
)
from blip_eraser.utils.i18n import TRANSLATIONS

_GIB = 1024**3


def _item(label, category, size):
    return ConfirmItem(label=label, category_label=category, size_bytes=size)


class TestLargeThreshold:
    def test_threshold_constant_is_5_gib(self):
        assert LARGE_DELETE_THRESHOLD_BYTES == 5 * _GIB

    def test_under_threshold_is_not_large(self):
        assert not is_large_operation(5 * _GIB - 1)

    def test_exactly_threshold_is_large(self):
        assert is_large_operation(5 * _GIB)

    def test_above_threshold_is_large(self):
        # ~63.2 GiB: el caso real de la carpeta de Steam que motivó el umbral.
        assert is_large_operation(63_217_334_784)

    def test_zero_is_not_large(self):
        assert not is_large_operation(0)


class TestPlan:
    def test_total_is_sum_of_items(self):
        plan = build_confirmation_plan(
            [_item("a", "Basura", 10), _item("b", "Caché", 20), _item("c", "Basura", 15)]
        )
        assert plan.total_bytes == 45

    def test_category_summary_groups_and_orders_by_size(self):
        plan = build_confirmation_plan(
            [
                _item("a", "Carpeta suelta", 10),
                _item("b", "Caché", 3 * _GIB),
                _item("c", "Carpeta suelta", 100),
            ]
        )
        assert plan.category_lines[0] == ("Caché", 1, 3 * _GIB)
        assert plan.category_lines[1] == ("Carpeta suelta", 2, 110)

    def test_is_large_flag_matches_threshold(self):
        assert not build_confirmation_plan([_item("x", "C", 100)]).is_large
        assert build_confirmation_plan([_item("x", "C", 5 * _GIB)]).is_large

    def test_plan_carries_the_items(self):
        items = [_item("steam", "Carpeta suelta", 63 * _GIB)]
        plan = build_confirmation_plan(items)
        assert plan.items is items

    def test_build_category_summary_helper(self):
        assert build_category_summary(
            [_item("a", "Basura", 10), _item("b", "Basura", 20), _item("c", "Caché", 5)]
        ) == [("Basura", 2, 30), ("Caché", 1, 5)]


class TestNeverSkipConfirmation:
    def test_always_confirm_policy_is_on(self):
        assert ALWAYS_CONFIRM_DESTRUCTIVE is True

    def test_plan_has_no_skip_fields(self):
        plan = build_confirmation_plan([_item("x", "C", 1)])
        for name in vars(plan):
            assert "skip" not in name
            assert "ask_again" not in name
            assert "remember" not in name

    def test_no_dont_ask_again_i18n_keys(self):
        for lang in TRANSLATIONS.values():
            for key in lang:
                low = key.lower()
                assert "dont_ask" not in low
                assert "never_ask" not in low
                assert "skip_confirm" not in low