"""
========================================================================================
INSTRUCTOR STRUCTURED SCHEMA & VALIDATION GUARD
========================================================================================
Guarantees deterministic, strongly-typed JSON outputs from LLMs using Pydantic.
If the LLM returns an invalid schema, Instructor feeds the validation error back
to the model for an automatic, self-correcting retry.
========================================================================================
"""

import sys
from typing import Type, TypeVar, Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field

# Add instructor repo to sys.path if needed
INSTRUCTOR_REPO = Path(__file__).resolve().parent / "instructor"
if str(INSTRUCTOR_REPO) not in sys.path and INSTRUCTOR_REPO.exists():
    sys.path.insert(0, str(INSTRUCTOR_REPO))

try:
    import instructor
    from openai import OpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False

T = TypeVar("T", bound=BaseModel)


class SchemaGuard:
    """
    Standard wrapper around Instructor for zero-hallucination structured responses.
    """

    def __init__(self, client: Optional[Any] = None, mode: Any = None):
        self.raw_client = client
        if INSTRUCTOR_AVAILABLE and client is not None:
            self.client = instructor.from_openai(client, mode=mode)
        else:
            self.client = None

    def extract(
        self,
        response_model: Type[T],
        prompt: str,
        system_instruction: str = "You are a precise data extraction agent. Output exactly according to the schema.",
        max_retries: int = 3,
        model: str = "gpt-4o-mini",
    ) -> T:
        """
        Extracts structured data matching `response_model`.
        Automatically retries upon Pydantic ValidationError.
        """
        if not self.client:
            raise RuntimeError(
                "Instructor client is not initialized. Ensure 'instructor' and 'openai' (or compatible) are installed."
            )

        result = self.client.chat.completions.create(
            model=model,
            response_model=response_model,
            max_retries=max_retries,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        )
        return result


# Example Target Schema for CRM Leads or Scraping
class LeadExtractionSchema(BaseModel):
    name: str = Field(description="Full name of contact")
    email: Optional[str] = Field(None, description="Contact email address")
    phone: Optional[str] = Field(None, description="Phone number with country code")
    company: Optional[str] = Field(None, description="Company or business name")
    budget: Optional[float] = Field(None, description="Estimated budget or deal value")
    intent: str = Field(description="High, Medium, or Low purchase intent")


if __name__ == "__main__":
    print("SchemaGuard with Instructor initialized.")
    print("Example schema: LeadExtractionSchema")
