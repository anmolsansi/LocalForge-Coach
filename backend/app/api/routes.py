import asyncio
import logging
import os
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.schemas.run import ModelsResponse, RunRequest, RunResponse, RunState, StepState
from app.services.ollama_client import OllamaClient
from app.services.pipeline import run_pipeline
from app.services.run_store import add_run, get_run

router = APIRouter()
logger = logging.getLogger("app.routes")


@router.post("/run", response_model=RunResponse)
async def create_run(request: RunRequest) -> RunResponse:
    run_id = str(uuid4())
    steps = {
        "step1": StepState(),
        "step2": StepState(),
        "step3": StepState(),
        "step4": StepState(),
        "step5": StepState(),
        "step6": StepState(),
    }
    run_state = RunState(run_id=run_id, steps=steps)
    await add_run(run_state)

    logger.info(
        "run_created run_id=%s model=%s judge_strictness=%s max_retries=%s question_len=%s jd_len=%s resume_len=%s",
        run_id,
        request.model,
        request.judge_strictness,
        request.max_retries,
        len(request.question),
        len(request.jd_text),
        len(request.resume_text),
    )

    asyncio.create_task(run_pipeline(run_id, request))
    return RunResponse(run_id=run_id)


@router.get("/run/{run_id}", response_model=RunState)
async def get_run_state(run_id: str) -> RunState:
    run = await get_run(run_id)
    if not run:
        logger.info("run_not_found run_id=%s", run_id)
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    env_models = os.getenv("OLLAMA_MODELS")
    if env_models:
        models = [m.strip() for m in env_models.split(",") if m.strip()]
        logger.info("models_from_env count=%s", len(models))
        return ModelsResponse(models=models)

    client = OllamaClient()
    try:
        models = await client.list_models()
        logger.info("models_from_ollama count=%s", len(models))
        return ModelsResponse(models=models)
    except Exception as exc:
        logger.exception("models_error error=%s", exc)
        return ModelsResponse(models=[], error=str(exc))
