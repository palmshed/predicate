import os
import json
from typing import List, Optional, Literal, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from app.agent.prompts import SYSTEM_PROMPT

# Provider configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

PROVIDER_CONFIG = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
}


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


BLUEPRINT_SCHEMA = json.dumps(QueryBlueprint.model_json_schema(), indent=2)


class AgentService:
    def __init__(self):
        config = PROVIDER_CONFIG.get(LLM_PROVIDER, PROVIDER_CONFIG["openai"])
        api_key = os.getenv(config["api_key_env"])

        headers = {}
        if LLM_PROVIDER == "openrouter":
            headers = {
                "HTTP-Referer": "https://predicate.palmshed.dev",
                "X-Title": "Predicate AI Engine",
            }

        self.client = OpenAI(
            api_key=api_key,
            base_url=config["base_url"],
            default_headers=headers,
        )
        self.model = LLM_MODEL
        self.supports_structured = LLM_PROVIDER == "openai"

    def translate_text_to_blueprint(self, user_question: str) -> QueryBlueprint:
        if self.supports_structured:
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

        parse_prompt = f"""{SYSTEM_PROMPT}

You MUST respond with a single JSON object matching this exact schema. No markdown, no explanation, just raw JSON:

{BLUEPRINT_SCHEMA}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": parse_prompt},
                {"role": "user", "content": user_question}
            ],
            temperature=0.0,
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        return QueryBlueprint.model_validate_json(raw)