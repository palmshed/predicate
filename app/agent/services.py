import os
from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from app.agent.prompts import SYSTEM_PROMPT


class FilterItem(BaseModel):
    column: str = Field(description="The exact database column name to apply the filter on.")
    operator: Literal["equals", "greater_than", "less_than", "contains"] = Field(
        description="The mathematical comparison operator."
    )
    value: Any = Field(description="The primitive criteria value (string, integer, float, etc.) to evaluate.")


class SortingConfig(BaseModel):
    column: str = Field(description="Column name used to order the rows.")
    direction: Literal["asc", "desc"] = Field(default="asc", description="Sort direction.")


class PaginationConfig(BaseModel):
    limit: int = Field(default=20, ge=1, le=100, description="Max rows to return. Cap at 100.")
    offset: int = Field(default=0, ge=0, description="Number of rows to skip.")


class AggregationConfig(BaseModel):
    type: Optional[Literal["count", "sum", "avg"]] = Field(
        default=None,
        description="The mathematical aggregate calculation requested by the user."
    )
    column: Optional[str] = Field(
        default=None,
        description="The database target column to aggregate. Use '*' only if the type requested is 'count'."
    )


class QueryBlueprint(BaseModel):
    target_table: Literal["customers", "orders", "products"] = Field(
        description="The primary target base table needed to fulfill the inquiry."
    )
    projection_columns: List[str] = Field(
        default=[],
        description="Columns to pull. For fields on related tables use explicit dot notation, e.g., 'customers.country'."
    )
    filters: List[FilterItem] = Field(
        default=[],
        description="Conditions. Use dot notation for related table fields, e.g., 'customers.country'."
    )
    aggregation: Optional[AggregationConfig] = Field(
        default=None,
        description="Populate this sub-block if the user asks for mathematical summaries like totals, counts, or averages."
    )
    sorting: Optional[SortingConfig] = Field(default=None)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)


class AgentService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"

    def translate_text_to_blueprint(self, user_question: str) -> QueryBlueprint:
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_question}
            ],
            response_format=QueryBlueprint,
            temperature=0.0
        )
        return response.choices[0].message.parsed