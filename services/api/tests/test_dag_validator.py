import pytest
from app.claims.dag_validator import (
    validate_claim_dag,
    topological_sort_claims,
    validate_dependencies_exist,
)
from app.schemas.agent_contracts import ClaimItem


def test_linear_valid_dag():
    """C1 (tiên đề) <- C2 (hệ quả) <- C3 (kết luận)"""
    claims = [
        ClaimItem(label="C1", content="a > 0, b > 0", claim_type="fact", depends_on=[]),
        ClaimItem(label="C2", content="(a-b)^2 >= 0", claim_type="inference", depends_on=["C1"]),
        ClaimItem(label="C3", content="a^2 + b^2 >= 2ab", claim_type="inference", depends_on=["C2"]),
    ]
    is_valid, cycle = validate_claim_dag(claims)
    assert is_valid is True
    assert cycle is None

    sorted_order = topological_sort_claims(claims)
    assert sorted_order.index("C1") < sorted_order.index("C2")
    assert sorted_order.index("C2") < sorted_order.index("C3")


def test_branching_merging_valid_dag():
    """Kim tự tháp suy luận hợp lệ nhiều nhánh."""
    claims = {
        "C1": [],
        "C2": [],
        "C3": ["C1"],
        "C4": ["C2"],
        "C5": ["C3", "C4"],
    }
    is_valid, cycle = validate_claim_dag(claims)
    assert is_valid is True
    assert cycle is None

    order = topological_sort_claims(claims)
    assert order.index("C1") < order.index("C3")
    assert order.index("C2") < order.index("C4")
    assert order.index("C3") < order.index("C5")
    assert order.index("C4") < order.index("C5")


def test_direct_two_node_cycle():
    """C1 phụ thuộc C2, C2 phụ thuộc C1 (Ngụy biện vòng quanh trực tiếp)."""
    claims = [
        ClaimItem(label="C1", content="Định lý Fermat đúng vì mệnh đề C2", claim_type="inference", depends_on=["C2"]),
        ClaimItem(label="C2", content="Mệnh đề C2 đúng vì định lý Fermat C1", claim_type="inference", depends_on=["C1"]),
    ]
    is_valid, cycle = validate_claim_dag(claims)
    assert is_valid is False
    assert cycle is not None
    assert len(cycle) >= 3
    assert cycle[0] == cycle[-1]  # Loop closed


def test_three_node_cycle():
    """C1 -> C2 -> C3 -> C1."""
    claims = {
        "C1": ["C3"],
        "C2": ["C1"],
        "C3": ["C2"],
    }
    is_valid, cycle = validate_claim_dag(claims)
    assert is_valid is False
    assert cycle is not None
    assert set(cycle).issuperset({"C1", "C2", "C3"})

    with pytest.raises(ValueError, match="Circular Dependency"):
        topological_sort_claims(claims)


def test_self_referencing_claim():
    """Mệnh đề tự dựa vào chính nó C1 -> C1."""
    claims = [
        ClaimItem(label="C1", content="Tự khẳng định đúng", claim_type="conjecture", depends_on=["C1"])
    ]
    is_valid, cycle = validate_claim_dag(claims)
    assert is_valid is False
    assert cycle == ["C1", "C1"]


def test_missing_dependency_validation():
    """Phát hiện mệnh đề phụ thuộc vào một nhãn không hề tồn tại."""
    claims = [
        ClaimItem(label="C1", content="Tam giác vuông", claim_type="fact", depends_on=[]),
        ClaimItem(label="C2", content="Theo công thức Heron C99", claim_type="inference", depends_on=["C99"]),
    ]
    errors = validate_dependencies_exist(claims)
    assert len(errors) == 1
    assert "C99" in errors[0]


def test_independent_unconnected_claims():
    """Nhiều tiên đề độc lập không phụ thuộc nhau."""
    claims = {
        "C1": [],
        "C2": [],
        "C3": [],
    }
    is_valid, cycle = validate_claim_dag(claims)
    assert is_valid is True
    assert cycle is None
    order = topological_sort_claims(claims)
    assert len(order) == 3
