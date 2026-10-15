import pytest

from datagen.personas.base import MATCHMAKER, customer
from datagen.rows import LineSpec

LINES = (LineSpec("primary", "light"),)


def _persona(tenure: int, **kwargs):
    return customer(
        99, "single", tenure, 0.1, LINES, title="Persona used only by this test", theme=MATCHMAKER,
        scenario="x" * 60, **kwargs,
    )


@pytest.mark.parametrize("tenure", [1, 2, 3])
def test_older_support_contacts_need_more_than_three_months_of_tenure(tenure):
    with pytest.raises(ValueError, match="support_older"):
        _persona(tenure, support_older=1)


def test_older_support_contacts_are_fine_with_longer_tenure_or_none():
    assert _persona(4, support_older=1).spec.support_older == 1
    assert _persona(2, support_older=0).spec.support_older == 0
    assert _persona(2).spec.support_older is None
