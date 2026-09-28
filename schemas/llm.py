"""Model-owned proposal fields, separate from authorization and actual evidence."""

from typing import Literal
from pydantic import Field, model_validator
from schemas.incident import NonEmpty, Schema


class LLMProposal(Schema):
    status: Literal["RECOMMEND", "ABSTAIN"]
    action_name: NonEmpty | None
    likely_root_cause: NonEmpty | None
    explanation: NonEmpty = Field(max_length=3000)
    evidence_ids: list[NonEmpty] = Field(max_length=5)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def coherent_decision(self):
        if self.status == "RECOMMEND" and (not self.action_name or not self.likely_root_cause):
            raise ValueError("Recommendation requires an action and root-cause hypothesis")
        if self.status == "ABSTAIN" and self.action_name is not None:
            raise ValueError("Abstention must not include an action")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Evidence IDs must be unique")
        return self
