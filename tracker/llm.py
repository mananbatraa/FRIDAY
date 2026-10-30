"""Optional: let Claude read each job email for better company/role/status accuracy.

Used only when ANTHROPIC_API_KEY is set and the `anthropic` package is installed
(it needs Python 3.10+). Otherwise the rules in job_emails.py do the work.
"""
from __future__ import annotations

import os
from typing import Literal, Optional

from . import job_emails
from .models import Email

SYSTEM = (
    "You read emails from a job seeker's inbox and pull out job-application facts. "
    "Company is the hiring company, never the job site or applicant-tracking system that sent it "
    "(Greenhouse, Workday, Lever, Ashby, Tsenta and similar). Role is the job title as written, or empty "
    "if the email doesn't name one. Kind: Applied for a confirmation that an application was received; "
    "Assessment for a test or take-home; Interview for an interview invite or scheduling; Offer for an offer; "
    "Rejected for a rejection; Verification for security codes, identity or account checks; Other for anything "
    "not about a specific application. next_action is a short instruction for the job seeker if the email asks them "
    "to do something (with any deadline), otherwise empty."
)


def available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class Claude:
    def __init__(self, model: str):
        import anthropic
        from pydantic import BaseModel

        class JobEmail(BaseModel):
            kind: Literal["Applied", "Assessment", "Interview", "Offer", "Rejected", "Verification", "Other"]
            company: str
            role: str
            next_action: str

        self._schema = JobEmail
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model = model

    def read(self, email: Email) -> Optional[dict]:
        """Return {kind, company, role, next_action}, or None so the caller falls back to rules."""
        prompt = f"From: {email.sender}\nSubject: {email.subject}\nDate: {email.date}\n\n{email.text[:6000]}"
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=self._schema,
            )
        except self._anthropic.APIError as e:
            print(f"  ! Claude call failed for '{email.subject}': {e}. Using rules instead.")
            return None
        if response.stop_reason == "refusal" or response.parsed_output is None:
            return None
        return response.parsed_output.model_dump()


def rules(email: Email) -> dict:
    found = job_emails.extract(email)
    kind = job_emails.classify(email)
    return {"kind": kind, "company": found.company, "role": found.role, "next_action": job_emails.next_action(email, kind)}
