from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.advisor import run_advisor
from app.agents.explainer import explain_plan
from app.agents.llm import get_llm, llm_status
from app.agents.tools import build_tools
from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.services.recommend import build_plan

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


def _require_profile(user: User):
    if user.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Create your financial profile first")


@router.get("/status")
def agent_status():
    """Whether the AI layer is configured (provider, model), without revealing any key."""
    return llm_status()


@router.get("/explain-plan")
def explain(tax_regime: Literal["new", "old"] = "new", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Plain-language explanation of /api/recommend. Falls back to a rule-based summary when AI is off or fails."""
    _require_profile(user)
    return explain_plan(build_plan(db, user, old_tax_regime=tax_regime == "old"))


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ask the advisor agent. Every figure in the reply is checked against tool results (`grounded`)."""
    _require_profile(user)
    if body.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The last message must be from the user")
    llm = get_llm()
    if llm is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"AI assistant is off. {llm_status()['reason']}")
    try:
        return run_advisor(llm, build_tools(db, user), [m.model_dump() for m in body.messages])
    except Exception as e:
        if type(e).__name__ == "RateLimitError":
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "The free AI quota is used up for now. Try again in a minute.")
        if type(e).__name__ == "GraphRecursionError":
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The assistant got stuck calling tools. Try rephrasing.")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"AI provider error ({type(e).__name__}). Try again shortly.")
