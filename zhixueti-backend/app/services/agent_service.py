"""Multi-agent scheduling service."""

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundException
from app.models.agent import AgtCollaborationLog
from app.models.sys import SysUser
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import AgentDefinitionResponse, AgentRunResponse, TaskCreateRequest, TaskResponse, TaskStageResponse


class AgentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.agent_repo = AgentRepository(db)

    def list_agents(self, include_disabled: bool = False) -> list[AgentDefinitionResponse]:
        agents = self.agent_repo.list_agents(include_disabled=include_disabled)
        return [AgentDefinitionResponse.model_validate(a) for a in agents]

    def update_agent_definition(self, agent_code: str, req) -> AgentDefinitionResponse:
        agent = self.agent_repo.get_agent_by_code(agent_code)
        if not agent:
            raise NotFoundException(ErrorCode.AGENT_NOT_FOUND)
        updates = req.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in updates.items():
            setattr(agent, field, value)
        self.db.commit()
        self.db.refresh(agent)
        return AgentDefinitionResponse.model_validate(agent)

    def create_task(self, user: SysUser, req: TaskCreateRequest) -> TaskResponse:
        task = self.agent_repo.create_task(user.id, req.task_type, req.task_name, req.input_params)
        return self._to_task_response(task)

    def get_task(self, user: SysUser, task_no: str) -> TaskResponse:
        task = self.agent_repo.get_task_by_no(task_no)
        if not task or task.user_id != user.id:
            raise NotFoundException(ErrorCode.TASK_NOT_FOUND)
        return self._to_task_response(task)

    def cancel_task(self, user: SysUser, task_no: str) -> TaskResponse:
        task = self.agent_repo.get_task_by_no(task_no)
        if not task or task.user_id != user.id:
            raise NotFoundException(ErrorCode.TASK_NOT_FOUND)
        if task.status in (0, 1):
            self.agent_repo.update_task(task.id, status=5, error_message="用户取消")
        return self._to_task_response(self.agent_repo.get_task_by_no(task_no))

    def publish_collaboration(
        self,
        task_id: int,
        collaboration_type: str,
        topic: str,
        initiator_run_id: int,
        initiator_msg: str,
        responder_run_id: int | None = None,
        responder_msg: str | None = None,
    ) -> AgtCollaborationLog:
        collab = AgtCollaborationLog(
            task_id=task_id,
            collaboration_type=collaboration_type,
            initiator_run_id=initiator_run_id,
            responder_run_id=responder_run_id,
            topic=topic,
            initiator_msg=initiator_msg,
            responder_msg=responder_msg,
            resolution_status=1 if responder_msg else 0,
        )
        return self.agent_repo.add_collaboration(collab)

    def _to_task_response(self, task) -> TaskResponse:
        stages = self.agent_repo.get_task_stages(task.id)
        runs = self.agent_repo.get_agent_runs(task.id)
        agent_map = {a.id: a for a in self.agent_repo.list_agents()}
        output = task.output_result or {}
        return TaskResponse(
            id=task.id,
            task_no=task.task_no,
            task_type=task.task_type,
            task_name=task.task_name,
            status=task.status,
            progress=task.progress,
            current_stage=task.current_stage,
            output_result=task.output_result,
            error_message=task.error_message,
            stages=[
                TaskStageResponse(
                    stage_code=s.stage_code,
                    stage_name=s.stage_name,
                    stage_order=s.stage_order,
                    status=s.status,
                    progress=s.progress,
                    message=s.message,
                )
                for s in stages
            ],
            agent_runs=[
                AgentRunResponse(
                    id=r.id,
                    agent_code=agent_map[r.agent_id].agent_code if r.agent_id in agent_map else "unknown",
                    agent_name=agent_map[r.agent_id].agent_name if r.agent_id in agent_map else "未知",
                    status=r.status,
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    duration_ms=r.duration_ms,
                    output_preview=self._preview_output(r.output_data),
                )
                for r in runs
            ],
            partial_previews=output.get("partial_previews", []),
            learning_diagnosis=output.get("learning_diagnosis"),
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )

    @staticmethod
    def _preview_output(output: dict | None) -> str | None:
        if not output:
            return None
        if "diagnosis" in output:
            d = output["diagnosis"]
            return d.get("teaching_strategy") if isinstance(d, dict) else str(d)[:100]
        if "content_md" in output:
            return str(output["content_md"])[:120]
        if "questions" in output:
            return f"已生成 {output.get('count', len(output.get('questions', [])))} 道题"
        if "mermaid" in output:
            return str(output["mermaid"])[:120]
        return str(list(output.keys())[:3])
