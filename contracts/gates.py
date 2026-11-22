"""Governance gates (plan 14.3). Each answer carries one GateResult per gate it passed.

G1 policy (what may be read), G2 read (what was read), G3 model gateway (which model, local
only), G4 answer check (citation by id, relevance, instructions inside notes), G5 human
confirmation, G6 audit trail.
"""

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from contracts.items import Item


class Gate(StrEnum):
    G1_POLICY = "G1"
    G2_READ = "G2"
    G3_MODEL = "G3"
    G4_ANSWER = "G4"
    G5_HUMAN = "G5"
    G6_AUDIT = "G6"


class Outcome(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate: Gate
    outcome: Outcome
    detail: str  # plain words with counts, never note text


class ProposedCitation(BaseModel):
    """What the model returns: ids only. It never writes the quote itself."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    unit: int


class ProposedPoint(BaseModel):
    """One point of a brief as proposed by the model, before the answer gate."""

    model_config = ConfigDict(frozen=True)

    label: str  # a few words naming the point, e.g. "Course"
    status: str  # done | open | changed | superseded
    citations: tuple[ProposedCitation, ...]


@runtime_checkable
class AnswerGate(Protocol):
    def check(
        self, question: str, proposed: list[ProposedPoint], given: dict[str, Item]
    ) -> tuple[list[ProposedPoint], GateResult]:
        """Keep only points whose citations exist and are relevant; report what was dropped."""
        ...
