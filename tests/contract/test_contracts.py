"""Contract tests: the shapes and interfaces every part relies on (gate G-C)."""

from collections.abc import Iterator
from datetime import datetime

import pytest
from pydantic import ValidationError

import contracts
from contracts import api
from contracts.adapters import OsPermission, ReadGrant, Scope, SourceAdapter
from contracts.broker import SourceState, SourceStatus
from contracts.errors import DeskThreadError, ErrorCode
from contracts.gates import Gate, GateResult, Outcome
from contracts.items import Item, ItemKind, SourceKind, Uncounted, Unit


def _item(**changes: object) -> Item:
    base: dict[str, object] = {
        "source_id": "folder:notes",
        "item_id": "n1",
        "kind": ItemKind.NOTE,
        "title": "sample",
        "units": (Unit(number=1, text="first"), Unit(number=2, text="second")),
    }
    return Item.model_validate(base | changes)


def test_contract_version_is_set() -> None:
    assert contracts.CONTRACT_VERSION == "1.20"


def test_item_units_are_numbered_from_one_and_looked_up_by_number() -> None:
    item = _item()
    first, missing = item.unit(1), item.unit(3)
    assert first is not None and first.text == "first"
    assert missing is None and item.unit(0) is None


def test_item_rejects_gaps_in_unit_numbers() -> None:
    with pytest.raises(ValidationError):
        _item(units=(Unit(number=1, text="a"), Unit(number=3, text="b")))


def test_item_without_a_date_is_undated_and_items_are_immutable() -> None:
    item = _item()
    assert item.undated
    assert not _item(date=datetime(2026, 11, 6, 9, 0)).undated
    with pytest.raises(ValidationError):
        item.title = "changed"


def test_error_codes_are_unique_and_carried_by_the_exception() -> None:
    values = [c.value for c in ErrorCode]
    assert len(values) == len(set(values))
    err = DeskThreadError(ErrorCode.PATH_OUTSIDE_ALLOWED, "refused")
    assert err.code is ErrorCode.PATH_OUTSIDE_ALLOWED
    assert str(err) == "E-104 refused"


class _Grant:
    source_id = "fake"
    scope_ids: frozenset[str] = frozenset({"a"})
    cancelled = False

    def raise_if_cancelled(self) -> None:
        return None


class _Adapter:
    source_id = "fake"
    kind = SourceKind.NOTES
    label = "Fake notes"

    def os_permission(self) -> OsPermission:
        return OsPermission.NOT_NEEDED

    def list_scopes(self) -> list[Scope]:
        return [Scope(scope_id="a", label="A", item_count=1)]

    def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
        grant.raise_if_cancelled()
        yield _item(source_id=self.source_id)


def test_a_minimal_adapter_and_grant_satisfy_the_interfaces() -> None:
    adapter, grant = _Adapter(), _Grant()
    assert isinstance(adapter, SourceAdapter)
    assert isinstance(grant, ReadGrant)
    assert [i.item_id for i in adapter.read(grant) if isinstance(i, Item)] == ["n1"]


def test_every_route_names_a_model_that_exists() -> None:
    for route, shape in api.ROUTES.items():
        method, path = route.split(" ")
        assert method in {"GET", "POST"} and path.startswith("/api/")
        name = shape.removeprefix("list[").removesuffix("]")
        assert name == "bytes" or hasattr(api, name), route


def test_source_state_defaults_and_gate_result_shape() -> None:
    state = SourceState(
        source_id="s",
        kind=SourceKind.MAIL,
        label="Mail",
        status=SourceStatus.OFF,
        os_permission=OsPermission.UNKNOWN,
    )
    assert state.items_in_memory == 0 and state.allowed_scope_ids == ()
    result = GateResult(gate=Gate.G4_ANSWER, outcome=Outcome.PASS, detail="4 of 4 kept")
    assert result.model_dump()["gate"] == "G4"


def test_answer_serialises_with_coverage_and_trace() -> None:
    answer = api.Answer(
        kind=api.AnswerKind.NOT_FOUND,
        question="q",
        points=(),
        message="I could not find this in the notes you shared.",
        coverage=api.Coverage(
            accessible=10,
            searched=9,
            unsupported=1,
            given_to_model=0,
            cited=0,
            by_source={"folder:notes": 10},
            not_accessible={"private:whatsapp": None},
        ),
        gate_trace=(),
        given_item_ids=(),
        seconds=0.1,
    )
    data = answer.model_dump(mode="json")
    assert data["kind"] == "not_found"
    assert data["coverage"]["accessible"] == 10
