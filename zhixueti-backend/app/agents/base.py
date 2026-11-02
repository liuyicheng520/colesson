"""Base class for all specialist agents."""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from app.agents.context import OrchestrationContext
from app.llm.gateway import LLMGateway
from app.repositories.agent_repository import AgentRepository


class BaseAgent(ABC):
    agent_code: str = ""
    agent_name: str = ""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.agent_repo = AgentRepository(db)
        self.llm = LLMGateway(db)

    def get_definition(self):
        return self.agent_repo.get_agent_by_code(self.agent_code)

    @abstractmethod
    async def execute(self, ctx: OrchestrationContext, parent_run_id: int | None = None) -> dict[str, Any]:
        """Run agent logic and return structured output."""

    async def _chat(
        self,
        ctx: OrchestrationContext,
        system: str,
        user: str,
        agent_run_id: int,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return await self.llm.chat(
            messages,
            user_id=ctx.user_id,
            task_id=ctx.task_id,
            agent_run_id=agent_run_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _start_run(self, ctx: OrchestrationContext, input_data: dict, parent_run_id: int | None = None):
        agent = self.get_definition()
        agent_id = agent.id if agent else 1
        return self.agent_repo.create_agent_run(ctx.task_id, agent_id, input_data, parent_run_id)

    def _finish_run(self, run_id: int, output: dict, status: int = 2) -> None:
        self.agent_repo.finish_agent_run(run_id, output, status)

    def _fail_run(self, run_id: int, error: str) -> None:
        run = self.agent_repo.finish_agent_run
        self.agent_repo.finish_agent_run(run_id, {"error": error}, status=3)
