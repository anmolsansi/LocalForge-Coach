import asyncio
from typing import Dict, Optional

from app.schemas.run import RunState

RUNS: Dict[str, RunState] = {}
RUNS_LOCK = asyncio.Lock()


async def add_run(run: RunState) -> None:
    async with RUNS_LOCK:
        RUNS[run.run_id] = run


async def get_run(run_id: str) -> Optional[RunState]:
    async with RUNS_LOCK:
        return RUNS.get(run_id)


async def update_run(run_id: str, **updates) -> None:
    async with RUNS_LOCK:
        run = RUNS.get(run_id)
        if not run:
            return
        for key, value in updates.items():
            setattr(run, key, value)


async def update_step(run_id: str, step_name: str, **updates) -> None:
    async with RUNS_LOCK:
        run = RUNS.get(run_id)
        if not run:
            return
        step = run.steps.get(step_name)
        if not step:
            return
        for key, value in updates.items():
            setattr(step, key, value)


async def mutate_run(run_id: str, mutator) -> None:
    async with RUNS_LOCK:
        run = RUNS.get(run_id)
        if not run:
            return
        mutator(run)
