from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Tuple

from app.schemas.run import AttemptSummary, JudgeReport, RunRequest, StepState
from app.services.ollama_client import OllamaClient
from app.services.prompt_loader import load_prompt
from app.services.run_store import update_run, update_step

JSON_NUDGE = "\n\nReturn valid JSON only. Do not wrap in code fences."
logger = logging.getLogger("app.pipeline")


def format_prompt(template: str, **values: str) -> str:
    try:
        return template.format(**values)
    except KeyError as exc:
        missing = exc.args[0]
        raise RuntimeError(f"Prompt missing placeholder: {missing}") from exc


async def run_json_step(
    client: OllamaClient,
    model: str,
    prompt: str,
    temperature: float,
) -> Tuple[Dict[str, Any], str]:
    raw = await client.generate(
        model=model,
        prompt=prompt,
        temperature=temperature,
        format_json=True,
    )
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        logger.warning("json_parse_failed model=%s retry=true", model)
        raw = await client.generate(
            model=model,
            prompt=prompt + JSON_NUDGE,
            temperature=temperature,
            format_json=True,
        )
        try:
            return json.loads(raw), raw
        except json.JSONDecodeError as exc:
            logger.error("json_parse_failed model=%s retry=false", model)
            raise ValueError("Invalid JSON returned by model") from exc


def clone_step(step: StepState) -> StepState:
    return StepState(**step.model_dump())


async def run_pipeline(run_id: str, req: RunRequest) -> None:
    client = OllamaClient()
    try:
        logger.info(
            "run_start run_id=%s model=%s judge_strictness=%s max_retries=%s",
            run_id,
            req.model,
            req.judge_strictness,
            req.max_retries,
        )
        await update_run(run_id, status="running", current_step=1, attempt=1)

        step1_task = asyncio.create_task(run_step1(run_id, client, req))
        step2_task = asyncio.create_task(run_step2(run_id, client, req))
        step3_task = asyncio.create_task(run_step3(run_id, client, req))

        step1_result, step2_result, step3_result = await asyncio.gather(
            step1_task,
            step2_task,
            step3_task,
        )
        step1_json, _ = step1_result
        step2_json, _ = step2_result
        step3_json, _ = step3_result

        attempt = 1
        while True:
            await update_run(run_id, current_step=4, attempt=attempt)
            final_output, judge_report = await run_answer_attempt(
                run_id,
                client,
                req,
                step1_json,
                step2_json,
                step3_json,
            )

            if judge_report.score is None:
                raise RuntimeError("Judge report missing score")

            if judge_report.score >= req.judge_strictness:
                logger.info(
                    "run_passed run_id=%s attempt=%s score=%s",
                    run_id,
                    attempt,
                    judge_report.score,
                )
                await update_run(
                    run_id,
                    status="done",
                    current_step=None,
                    final_output=final_output,
                    judge_report=judge_report,
                )
                return

            if attempt > req.max_retries:
                logger.info(
                    "run_max_retries run_id=%s attempt=%s score=%s",
                    run_id,
                    attempt,
                    judge_report.score,
                )
                await update_run(
                    run_id,
                    status="done",
                    current_step=None,
                    final_output=final_output,
                    judge_report=judge_report,
                )
                return

            await snapshot_attempt(run_id, attempt, final_output, judge_report)

            attempt += 1
            logger.info("run_retry run_id=%s next_attempt=%s", run_id, attempt)
            await update_run(run_id, attempt=attempt, current_step=2)
            step2_json, _ = await run_step2_retry(
                run_id,
                client,
                req,
                critique=json.dumps(judge_report.model_dump(), indent=2),
            )

    except Exception as exc:
        logger.exception("run_failed run_id=%s error=%s", run_id, exc)
        await update_run(run_id, status="failed", current_step=None, error=str(exc))


async def run_step1(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
) -> Tuple[Dict[str, Any], str]:
    await update_step(run_id, "step1", status="running")
    try:
        logger.info("step_start run_id=%s step=step1", run_id)
        prompt = format_prompt(
            load_prompt("step1_question_analysis.txt"),
            question=req.question,
        )
        output, raw = await run_json_step(client, req.model, prompt, temperature=0.2)
        await update_step(
            run_id,
            "step1",
            status="done",
            output_json=output,
            output_text=raw,
        )
        logger.info("step_done run_id=%s step=step1", run_id)
        return output, raw
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step1 error=%s", run_id, exc)
        await update_step(run_id, "step1", status="failed", error=str(exc))
        raise


async def run_step2(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
) -> Tuple[Dict[str, Any], str]:
    await update_step(run_id, "step2", status="running")
    try:
        logger.info("step_start run_id=%s step=step2", run_id)
        prompt = format_prompt(
            load_prompt("step2_jd_analysis.txt"),
            jd_text=req.jd_text,
        )
        output, raw = await run_json_step(client, req.model, prompt, temperature=0.2)
        await update_step(
            run_id,
            "step2",
            status="done",
            output_json=output,
            output_text=raw,
        )
        logger.info("step_done run_id=%s step=step2", run_id)
        return output, raw
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step2 error=%s", run_id, exc)
        await update_step(run_id, "step2", status="failed", error=str(exc))
        raise


async def run_step2_retry(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
    critique: str,
) -> Tuple[Dict[str, Any], str]:
    await update_step(run_id, "step2", status="running", error=None)
    try:
        logger.info("step_retry_start run_id=%s step=step2", run_id)
        prompt = format_prompt(
            load_prompt("step2_jd_analysis_retry.txt"),
            jd_text=req.jd_text,
            critique=critique,
        )
        output, raw = await run_json_step(client, req.model, prompt, temperature=0.2)
        await update_step(
            run_id,
            "step2",
            status="done",
            output_json=output,
            output_text=raw,
        )
        logger.info("step_done run_id=%s step=step2", run_id)
        return output, raw
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step2 error=%s", run_id, exc)
        await update_step(run_id, "step2", status="failed", error=str(exc))
        raise


async def run_step3(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
) -> Tuple[Dict[str, Any], str]:
    await update_step(run_id, "step3", status="running")
    try:
        logger.info("step_start run_id=%s step=step3", run_id)
        prompt = format_prompt(
            load_prompt("step3_resume_analysis.txt"),
            resume_text=req.resume_text,
        )
        output, raw = await run_json_step(client, req.model, prompt, temperature=0.2)
        await update_step(
            run_id,
            "step3",
            status="done",
            output_json=output,
            output_text=raw,
        )
        logger.info("step_done run_id=%s step=step3", run_id)
        return output, raw
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step3 error=%s", run_id, exc)
        await update_step(run_id, "step3", status="failed", error=str(exc))
        raise


async def run_step4(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
    step1_json: Dict[str, Any],
    step2_json: Dict[str, Any],
    step3_json: Dict[str, Any],
) -> Tuple[Dict[str, Any], str]:
    await update_step(run_id, "step4", status="running")
    try:
        logger.info("step_start run_id=%s step=step4", run_id)
        prompt = format_prompt(
            load_prompt("step4_answer.txt"),
            question=req.question,
            jd_text=req.jd_text,
            resume_text=req.resume_text,
            step1_json=json.dumps(step1_json, indent=2),
            step2_json=json.dumps(step2_json, indent=2),
            step3_json=json.dumps(step3_json, indent=2),
        )
        output, raw = await run_json_step(client, req.model, prompt, temperature=0.5)
        await update_step(
            run_id,
            "step4",
            status="done",
            output_json=output,
            output_text=raw,
        )
        logger.info("step_done run_id=%s step=step4", run_id)
        return output, raw
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step4 error=%s", run_id, exc)
        await update_step(run_id, "step4", status="failed", error=str(exc))
        raise


async def run_step5(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
    answer_json: Dict[str, Any],
) -> Tuple[str, str]:
    if not req.custom_prompt_text:
        await update_step(run_id, "step5", status="skipped")
        logger.info("step_skipped run_id=%s step=step5", run_id)
        return answer_json.get("answer", ""), json.dumps(answer_json, indent=2)

    await update_step(run_id, "step5", status="running")
    try:
        logger.info("step_start run_id=%s step=step5", run_id)
        prompt = format_prompt(
            load_prompt("step5_custom_transform.txt"),
            custom_prompt_text=req.custom_prompt_text,
            draft_answer=answer_json.get("answer", ""),
            evidence_map=json.dumps(answer_json.get("evidence_map", {}), indent=2),
        )
        output = await client.generate(
            model=req.model,
            prompt=prompt,
            temperature=0.4,
            format_json=False,
        )
        await update_step(
            run_id,
            "step5",
            status="done",
            output_text=output,
        )
        logger.info("step_done run_id=%s step=step5", run_id)
        return output, output
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step5 error=%s", run_id, exc)
        await update_step(run_id, "step5", status="failed", error=str(exc))
        raise


async def run_step6(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
    final_output: str,
    step1_json: Dict[str, Any],
    step2_json: Dict[str, Any],
    step3_json: Dict[str, Any],
) -> Tuple[JudgeReport, str]:
    await update_step(run_id, "step6", status="running")
    try:
        logger.info("step_start run_id=%s step=step6", run_id)
        prompt = format_prompt(
            load_prompt("step6_judge.txt"),
            question=req.question,
            jd_text=req.jd_text,
            resume_text=req.resume_text,
            final_output=final_output,
            step1_json=json.dumps(step1_json, indent=2),
            step2_json=json.dumps(step2_json, indent=2),
            step3_json=json.dumps(step3_json, indent=2),
            judge_strictness=str(req.judge_strictness),
        )
        output, raw = await run_json_step(client, req.model, prompt, temperature=0.1)
        report = JudgeReport(
            score=output.get("score"),
            reasons=output.get("reasons", []),
            fixes=output.get("fixes", []),
            raw_text=raw,
        )
        await update_step(
            run_id,
            "step6",
            status="done",
            output_json=output,
            output_text=raw,
        )
        logger.info("step_done run_id=%s step=step6 score=%s", run_id, report.score)
        return report, raw
    except Exception as exc:
        logger.exception("step_failed run_id=%s step=step6 error=%s", run_id, exc)
        await update_step(run_id, "step6", status="failed", error=str(exc))
        raise


async def run_answer_attempt(
    run_id: str,
    client: OllamaClient,
    req: RunRequest,
    step1_json: Dict[str, Any],
    step2_json: Dict[str, Any],
    step3_json: Dict[str, Any],
) -> Tuple[str, JudgeReport]:
    step4_json, _ = await run_step4(
        run_id,
        client,
        req,
        step1_json,
        step2_json,
        step3_json,
    )
    final_output, _ = await run_step5(run_id, client, req, step4_json)
    judge_report, _ = await run_step6(
        run_id,
        client,
        req,
        final_output,
        step1_json,
        step2_json,
        step3_json,
    )
    logger.info(
        "attempt_done run_id=%s attempt_score=%s",
        run_id,
        judge_report.score,
    )
    await update_run(run_id, final_output=final_output, judge_report=judge_report)
    return final_output, judge_report


async def snapshot_attempt(
    run_id: str,
    attempt: int,
    final_output: str,
    judge_report: JudgeReport,
) -> None:
    from app.services.run_store import mutate_run

    def _mutate(run) -> None:
        snapshot = AttemptSummary(
            attempt=attempt,
            steps={name: clone_step(step) for name, step in run.steps.items()},
            final_output=final_output,
            judge_report=judge_report,
        )
        run.attempt_history.append(snapshot)
        logger.info("attempt_snapshot run_id=%s attempt=%s", run_id, attempt)
        run.steps = {
            "step1": clone_step(run.steps["step1"]),
            "step2": StepState(),
            "step3": clone_step(run.steps["step3"]),
            "step4": StepState(),
            "step5": StepState(),
            "step6": StepState(),
        }

    await mutate_run(run_id, _mutate)
