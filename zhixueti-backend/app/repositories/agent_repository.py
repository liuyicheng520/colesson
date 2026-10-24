"""Agent task repository."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.agent import (
    AgtAgentDefinition,
    AgtAgentRun,
    AgtCollaborationLog,
    AgtLlmCallLog,
    AgtTask,
    AgtTaskStage,
)

TASK_STAGES = [
    ("parse", "参数解析", 1),
    ("plan", "任务规划", 2),
    ("generate", "内容生成", 3),
    ("validate", "一致性校验", 4),
    ("audit", "安全审核", 5),
    ("store", "数据入库", 6),
    ("push", "结果推送", 7),
]


class AgentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_agent_by_code(self, agent_code: str) -> AgtAgentDefinition | None:
        return (
            self.db.query(AgtAgentDefinition)
            .filter(AgtAgentDefinition.agent_code == agent_code)
            .first()
        )

    def list_agents(self, include_disabled: bool = False) -> list[AgtAgentDefinition]:
        query = self.db.query(AgtAgentDefinition)
        if not include_disabled:
            query = query.filter(AgtAgentDefinition.status == 1)
        return query.order_by(AgtAgentDefinition.id).all()

    def create_task(
        self,
        user_id: int,
        task_type: str,
        task_name: str,
        input_params: dict,
    ) -> AgtTask:
        task = AgtTask(
            task_no=str(uuid.uuid4()),
            user_id=user_id,
            task_type=task_type,
            task_name=task_name,
            input_params=input_params,
            status=0,
            progress=0,
        )
        self.db.add(task)
        self.db.flush()
        for code, name, order in TASK_STAGES:
            self.db.add(
                AgtTaskStage(
                    task_id=task.id,
                    stage_code=code,
                    stage_name=name,
                    stage_order=order,
                    status=0,
                    progress=0,
                )
            )
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task_by_no(self, task_no: str) -> AgtTask | None:
        return self.db.query(AgtTask).filter(AgtTask.task_no == task_no).first()

    def get_task_by_id(self, task_id: int) -> AgtTask | None:
        return self.db.query(AgtTask).filter(AgtTask.id == task_id).first()

    def get_task_stages(self, task_id: int) -> list[AgtTaskStage]:
        return (
            self.db.query(AgtTaskStage)
            .filter(AgtTaskStage.task_id == task_id)
            .order_by(AgtTaskStage.stage_order)
            .all()
        )

    def update_task_stage(
        self,
        task_id: int,
        stage_code: str,
        status: int,
        progress: int = 100,
        message: str | None = None,
    ) -> None:
        stage = (
            self.db.query(AgtTaskStage)
            .filter(AgtTaskStage.task_id == task_id, AgtTaskStage.stage_code == stage_code)
            .first()
        )
        if not stage:
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if status == 1 and not stage.started_at:
            stage.started_at = now
        if status in (2, 3, 4):
            stage.finished_at = now
        stage.status = status
        stage.progress = progress
        stage.message = message
        task = self.db.query(AgtTask).filter(AgtTask.id == task_id).first()
        if task:
            task.current_stage = stage_code
            stages = self.get_task_stages(task_id)
            total = max(task.total_stages or len(stages) or 1, 1)
            completed = sum(1 for s in stages if s.status == 2)
            # 进行中阶段按子进度计入，避免「内容生成」长时间卡在 28%
            running = next((s for s in stages if s.status == 1), None)
            partial = (max(0, min(100, int(running.progress or 0))) / 100.0) if running else 0.0
            pct = int((completed + partial) / total * 100)
            task.progress = min(pct, 99 if completed < total else 100)
        self.db.commit()

    def create_agent_run(
        self,
        task_id: int,
        agent_id: int,
        input_data: dict,
        parent_run_id: int | None = None,
    ) -> AgtAgentRun:
        run = AgtAgentRun(
            task_id=task_id,
            agent_id=agent_id,
            run_no=str(uuid.uuid4()),
            parent_run_id=parent_run_id,
            input_data=input_data,
            status=1,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def finish_agent_run(self, run_id: int, output_data: dict, status: int = 2) -> None:
        run = self.db.query(AgtAgentRun).filter(AgtAgentRun.id == run_id).first()
        if run:
            run.output_data = output_data
            run.status = status
            run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if run.started_at:
                run.duration_ms = int(
                    (run.finished_at - run.started_at).total_seconds() * 1000
                )
            self.db.commit()

    def log_llm_call(self, log: AgtLlmCallLog) -> AgtLlmCallLog:
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def add_collaboration(self, collab: AgtCollaborationLog) -> AgtCollaborationLog:
        self.db.add(collab)
        self.db.commit()
        self.db.refresh(collab)
        return collab

    def get_agent_runs(self, task_id: int) -> list[AgtAgentRun]:
        return (
            self.db.query(AgtAgentRun)
            .filter(AgtAgentRun.task_id == task_id)
            .order_by(AgtAgentRun.id)
            .all()
        )

    def update_task(
        self,
        task_id: int,
        status: int | None = None,
        output_result: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        task = self.db.query(AgtTask).filter(AgtTask.id == task_id).first()
        if not task:
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if status is not None:
            task.status = status
            if status == 1 and not task.started_at:
                task.started_at = now
            if status in (2, 3, 4, 5) and not task.finished_at:
                task.finished_at = now
                if task.started_at:
                    task.duration_ms = int((task.finished_at - task.started_at).total_seconds() * 1000)
        if output_result is not None:
            task.output_result = output_result
        if error_message is not None:
            task.error_message = error_message
        self.db.commit()
