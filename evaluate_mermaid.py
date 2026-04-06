#!/usr/bin/env python3
"""
evaluate_mermaid.py — LLM Mermaid diagram generation evaluator.

Usage:
    python evaluate_mermaid.py run-eval \\
        --dataset eval_dataset.json \\
        --output-dir ./eval_results \\
        --actor-model gemini-3-flash-preview:cloud \\
        --judge-model gpt-oss:120b-cloud
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import click
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — must come before pyplot import
import matplotlib.pyplot as plt
import pandas as pd

from local_llm import Copilot

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("evaluate_mermaid")

# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------
ACTOR_SYSTEM_PROMPT = """\
You are a Smart Home AI assistant. When given a user command, generate a \
Mermaid sequence diagram representing the system's execution flow.

Rules:
- Always include these base participants at the top:
    actor User
    participant Assistant
    participant Hub
- Define specific devices ONLY if relevant to the command.
  Format: participant [Alias] as [Description] (espID:X, id)
  Example: participant BedLight as Bed light (espID:3, led2)
- Execution flow: User -> Assistant -> Hub -> Device -> Hub -> Assistant -> User
- Actuators: Hub uses `set`  (e.g., Hub->>BedLight: set value = true)
- Sensors:   Hub uses `get`  (e.g., Hub->>Pir: get status)
- Use `par ... and ... end` blocks for multi-device parallel actions.
- Use `alt ... else ... end` blocks for conditional logic.

Output ONLY the Mermaid code block wrapped in ```mermaid ... ```.
Do NOT add any prose, explanation, or commentary outside the code fence.\
"""

JUDGE_SYSTEM_PROMPT = """\
You are an expert evaluator of Mermaid sequence diagrams for Smart Home IoT systems.
You will receive a GENERATED diagram and a GROUND TRUTH diagram.
Evaluate the logical correctness and completeness of the generated diagram.

Scoring rubric (1–5):
  5 — Perfect: All participants, flow direction, and values match the ground truth intent.
  4 — Good: Minor issues (slightly different wording, extra step) but logic is correct.
  3 — Partial: Core logic present but some participants or actions are missing/wrong.
  2 — Poor: Major logic errors, wrong devices, or inverted flow.
  1 — Fail: Completely wrong, empty, or totally off-topic diagram.

Respond with ONLY a valid JSON object in this EXACT format (no extra text):
{"score": <integer 1-5>, "reason": "<one concise sentence>"}\
"""

# ---------------------------------------------------------------------------
# Helper: extract Mermaid code from LLM response
# ---------------------------------------------------------------------------
def extract_mermaid(response: str) -> str | None:
    """
    Extract raw Mermaid code from a ```mermaid ... ``` fenced block.
    Falls back to treating the whole response as Mermaid if it starts with
    'sequenceDiagram'.
    """
    if not response:
        return None

    pattern = re.compile(r"```mermaid\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    match = pattern.search(response)
    if match:
        return match.group(1).strip()

    # Fallback: response IS the raw mermaid code
    stripped = response.strip()
    if stripped.lower().startswith("sequencediagram"):
        return stripped

    return None


# ---------------------------------------------------------------------------
# Helper: Mermaid syntax validation via mmdc
# ---------------------------------------------------------------------------
def validate_syntax_mmdc(mermaid_code: str, timeout: int = 10) -> tuple[bool | None, str]:
    """
    Save *mermaid_code* to a temporary .mmd file and run mmdc to validate syntax.

    Returns:
        (True,  detail)  — syntax is valid
        (False, detail)  — syntax error or mmdc returned non-zero
        (None,  detail)  — mmdc is not installed; syntax check skipped
    """
    tmp_mmd: str | None = None
    tmp_out: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mmd", delete=False, encoding="utf-8"
        ) as f:
            f.write(mermaid_code)
            tmp_mmd = f.name

        tmp_out = tmp_mmd.replace(".mmd", "_out.png")

        result = subprocess.run(
            ["mmdc.cmd", "-i", tmp_mmd, "-o", tmp_out],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True 
        )

        if result.returncode == 0:
            return True, "mmdc: OK"

        stderr = (result.stderr or "").strip()
        return False, f"mmdc stderr: {stderr[:300]}"

    except subprocess.TimeoutExpired:
        return False, "mmdc: timed out (>10s)"
    except FileNotFoundError:
        logger.warning("mmdc not found on PATH — skipping syntax validation.")
        return None, "mmdc not installed"
    except Exception as exc:
        return False, f"mmdc exception: {exc}"
    finally:
        for path in filter(None, [tmp_mmd, tmp_out]):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Helper: parse judge JSON response
# ---------------------------------------------------------------------------
def parse_judge_response(response: str) -> tuple[int | None, str]:
    """
    Extract {"score": N, "reason": "..."} from the judge's response.
    Tries several patterns to handle responses that may or may not be fenced.
    """
    if not response:
        return None, "empty judge response"

    patterns = [
        re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE),
        re.compile(r"```\s*(\{.*?\})\s*```", re.DOTALL),
        re.compile(r"(\{[^{}]*\"score\"[^{}]*\})", re.DOTALL),
    ]

    for pat in patterns:
        m = pat.search(response)
        if not m:
            continue
        try:
            obj = json.loads(m.group(1))
            score = int(obj["score"])
            reason = str(obj.get("reason", ""))
            if 1 <= score <= 5:
                return score, reason
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    return None, f"could not parse JSON from judge: {response[:200]}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@click.group()
def cli():
    """Mermaid diagram LLM evaluation toolkit."""


@cli.command("run-eval")
@click.option(
    "--dataset",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the evaluation dataset JSON file.",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Directory to save results (CSV, PNG).",
)
@click.option(
    "--actor-model",
    default="gemini-3-flash-preview:cloud",
    show_default=True,
    help="Model under test — generates the Mermaid diagrams.",
)
@click.option(
    "--judge-model",
    default="gpt-oss:120b-cloud",
    show_default=True,
    help="Model acting as the LLM judge for logic scoring.",
)
def run_eval(dataset: str, output_dir: str, actor_model: str, judge_model: str) -> None:
    """Run the full Mermaid diagram evaluation pipeline."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ Load
    logger.info("Loading dataset: %s", dataset)
    with open(dataset, "r", encoding="utf-8") as f:
        test_cases: list[dict] = json.load(f)
    logger.info("Loaded %d test cases.", len(test_cases))

    # ---------------------------------------------------------- Instantiate actor
    logger.info("Actor model  : %s", actor_model)
    logger.info("Judge model  : %s", judge_model)
    actor = Copilot(model=actor_model)
    judge: Copilot | None = None  # lazy — only created when first needed

    records: list[dict] = []

    for idx, tc in enumerate(test_cases, start=1):
        test_id   = tc.get("id", f"test_{idx:02d}")
        task_type = tc.get("task_type", "unknown")
        prompt    = tc.get("prompt", "")
        ground_truth = tc.get("ground_truth_mermaid", "")

        logger.info(
            "[%d/%d] %s (%s) — generating...",
            idx, len(test_cases), test_id, task_type,
        )

        record: dict = {
            "id":               test_id,
            "task_type":        task_type,
            "prompt":           prompt,
            "generated_raw":    None,
            "extracted_mermaid": None,
            "syntax_pass":      None,
            "syntax_detail":    None,
            "logic_score":      None,
            "judge_reason":     None,
        }

       # -------------------------------------------------------- Step A: Generation
        try:
            # XÓA (hoặc comment) dòng này:
            # current_appliances = get_all_appliances_status()
            
            # THÊM đoạn đọc file tĩnh này để không đụng tới phần cứng ESP:
            with open("appliances_data.json", "r", encoding="utf-8") as f:
                hardware_context = f.read()
            
            dynamic_system_prompt = ACTOR_SYSTEM_PROMPT + f"\n\nHere is the current system architecture and available devices:\n{hardware_context}"

            raw_response = actor.infer(
                user_prompt=prompt,
                system_prompt=dynamic_system_prompt,
            )
            record["generated_raw"] = raw_response
        except Exception as exc:
            logger.error("[%s] Generation error: %s", test_id, exc)
            records.append(record)
            continue

        if not raw_response:
            logger.warning("[%s] Actor returned an empty response.", test_id)
            record["syntax_detail"] = "actor returned empty response"
            records.append(record)
            continue

        # ------------------------------------------------- Step B: Regex Extraction
        extracted = extract_mermaid(raw_response)
        record["extracted_mermaid"] = extracted

        if not extracted:
            logger.warning("[%s] No Mermaid code block found in response.", test_id)
            record["syntax_pass"]   = False
            record["syntax_detail"] = "no ```mermaid``` block in response"
            records.append(record)
            continue

        # ---------------------------------------------- Step C: Syntax Validation
        logger.info("[%s] Validating syntax via mmdc...", test_id)
        syntax_ok, syntax_detail = validate_syntax_mmdc(extracted)
        record["syntax_pass"]   = syntax_ok
        record["syntax_detail"] = syntax_detail

        if syntax_ok is False:
            logger.warning("[%s] Syntax FAIL — %s", test_id, syntax_detail)
            records.append(record)
            continue

        # ------------------------------------ Step D: LLM-as-a-Judge (Logic Score)
        logger.info("[%s] Running LLM judge (%s)...", test_id, judge_model)
        if judge is None:
            judge = Copilot(model=judge_model)

        judge_user_prompt = (
            "### Generated Mermaid Diagram\n"
            f"```mermaid\n{extracted}\n```\n\n"
            "### Ground Truth Mermaid Diagram\n"
            f"```mermaid\n{ground_truth}\n```\n\n"
            "Evaluate the generated diagram against the ground truth and respond "
            "with the JSON object as instructed."
        )

        try:
            judge_response = judge.infer(
                user_prompt=judge_user_prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.error("[%s] Judge inference error: %s", test_id, exc)
            record["judge_reason"] = f"judge error: {exc}"
            records.append(record)
            continue

        score, reason = parse_judge_response(judge_response or "")
        record["logic_score"]  = score
        record["judge_reason"] = reason
        logger.info("[%s] Logic score: %s — %s", test_id, score, reason)

        records.append(record)

    # ---------------------------------------------------------------- DataFrame
    logger.info("Building results DataFrame...")
    df = pd.DataFrame(records)

    # --------------------------------------------------------------- CSV Export
    csv_path = output_path / "evaluation_results.csv"
    try:
        df.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info("Results CSV saved: %s", csv_path)
    except PermissionError:
        # File is likely open in Excel or another program — save with timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = output_path / f"evaluation_results_{ts}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        logger.warning(
            "evaluation_results.csv was locked. Saved to: %s", csv_path
        )

    # ---------------------------------------------------------------- Bar Chart
    judged = df[df["logic_score"].notna()].copy()
    judged["logic_score"] = judged["logic_score"].astype(float)

    if not judged.empty:
        avg_scores = (
            judged.groupby("task_type")["logic_score"]
            .mean()
            .sort_values(ascending=False)
        )

        palette = ["#4C72B0", "#DD8452", "#55A868", "#C44E52",
                   "#8172B2", "#937860", "#DA8BC3", "#8C8C8C"]

        fig, ax = plt.subplots(figsize=(9, 5))
        bars = ax.bar(
            avg_scores.index,
            avg_scores.values,
            color=palette[: len(avg_scores)],
            edgecolor="white",
            linewidth=0.8,
            width=0.55,
        )
        ax.set_ylim(0, 5.8)
        ax.set_xlabel("Task Type", fontsize=12)
        ax.set_ylabel("Average Logic Score  (1 – 5)", fontsize=12)
        ax.set_title(
            f"Average LLM Logic Score by Task Type\nActor: {actor_model}",
            fontsize=13,
            fontweight="bold",
            pad=14,
        )
        ax.axhline(y=3, color="grey", linestyle="--", linewidth=0.9, alpha=0.6,
                   label="Threshold (3)")
        ax.legend(fontsize=10)

        for bar, val in zip(bars, avg_scores.values):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + 0.1,
                f"{val:.2f}",
                ha="center",
                va="bottom",
                fontsize=11,
                fontweight="bold",
            )

        plt.tight_layout()
        chart_path = output_path / "score_by_task.png"
        fig.savefig(chart_path, dpi=150)
        plt.close(fig)
        logger.info("Chart saved: %s", chart_path)
    else:
        logger.warning("No judged results — bar chart skipped.")

    # --------------------------------------------------------- Console Summary
    _print_summary(df, actor_model)


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
def _print_summary(df: pd.DataFrame, actor_model: str) -> None:
    """Print a nicely formatted summary table to stdout."""
    W = 96
    sep  = "=" * W
    dash = "-" * W

    print(f"\n{sep}")
    print(f"  EVALUATION SUMMARY   |  Actor: {actor_model}")
    print(sep)

    header = (
        f"{'ID':<12} {'Task Type':<22} {'Syntax':>8} {'Score':>7}  Reason"
    )
    print(header)
    print(dash)

    for _, row in df.iterrows():
        sp = row["syntax_pass"]
        if sp is None:
            syntax_str = "SKIP"
        elif sp:
            syntax_str = "PASS"
        else:
            syntax_str = "FAIL"

        score_str = (
            str(int(row["logic_score"]))
            if pd.notna(row["logic_score"])
            else "N/A"
        )
        reason = str(row["judge_reason"] or "")[:52]
        print(
            f"{str(row['id']):<12} {str(row['task_type']):<22} "
            f"{syntax_str:>8} {score_str:>7}  {reason}"
        )

    print(sep)

    # Aggregate stats
    total            = len(df)
    syntax_pass_n    = int(df["syntax_pass"].eq(True).sum())
    syntax_fail_n    = int(df["syntax_pass"].eq(False).sum())
    syntax_skip_n    = int(df["syntax_pass"].isna().sum())
    judged           = df[df["logic_score"].notna()]
    avg_score        = judged["logic_score"].mean() if not judged.empty else float("nan")

    print(f"  Total test cases : {total}")
    print(
        f"  Syntax           : PASS={syntax_pass_n}  "
        f"FAIL={syntax_fail_n}  SKIP(no mmdc)={syntax_skip_n}"
    )

    if not judged.empty:
        print(
            f"  Judged           : {len(judged)} / {total}  |  "
            f"Overall avg score: {avg_score:.2f} / 5"
        )
        print("\n  Avg Logic Score by Task Type:")
        by_type = (
            judged.groupby("task_type")["logic_score"]
            .mean()
            .sort_values(ascending=False)
        )
        for tt, s in by_type.items():
            bar = "█" * int(round(s * 4))
            print(f"    {str(tt):<22}  {s:.2f}  {bar}")
    else:
        print("  No cases were judged (all failed syntax or generation).")

    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cli()
