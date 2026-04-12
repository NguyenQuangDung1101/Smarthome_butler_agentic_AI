"""Validate eval dataset testcases against expected schemas.

Usage:
  python eval_testcase.py [path/to/eval_dataset.json]

Exits with code 0 when all testcases pass structural validation, 1 otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # Some datasets wrap cases in a dict
        # try to find a top-level list value
        for v in data.values():
            if isinstance(v, list):
                return v
        raise ValueError("JSON root is an object and no list found")
    if not isinstance(data, list):
        raise ValueError("Expected top-level list of testcases")
    return data


def error(msg: str) -> str:
    return msg


def validate_preconditions(pre: Dict[str, Any], tc_id: str) -> List[str]:
    errs: List[str] = []
    if not isinstance(pre, dict):
        return [error(f"{tc_id}: preconditions must be an object")]
    notes = pre.get("notes_setup")
    state = pre.get("state_setup")
    if notes is None:
        errs.append(error(f"{tc_id}: preconditions.notes_setup missing"))
    elif not isinstance(notes, list):
        errs.append(error(f"{tc_id}: preconditions.notes_setup must be a list"))
    else:
        for i, n in enumerate(notes):
            if not isinstance(n, dict):
                errs.append(error(f"{tc_id}: notes_setup[{i}] must be object"))
                continue
            d = n.get("date")
            t = n.get("note_text")
            if d is None or t is None:
                errs.append(error(f"{tc_id}: notes_setup[{i}] must have date and note_text"))
            else:
                if d != "today" and not DATE_RE.match(d):
                    errs.append(error(f"{tc_id}: notes_setup[{i}].date must be yyyy-mm-dd or 'today'"))
                if not isinstance(t, str):
                    errs.append(error(f"{tc_id}: notes_setup[{i}].note_text must be string"))

    if state is None:
        errs.append(error(f"{tc_id}: preconditions.state_setup missing"))
    elif not isinstance(state, list):
        errs.append(error(f"{tc_id}: preconditions.state_setup must be a list"))
    else:
        for i, s in enumerate(state):
            if not isinstance(s, dict):
                errs.append(error(f"{tc_id}: state_setup[{i}] must be object"))
                continue
            esp = s.get("espID")
            dev = s.get("device_type")
            name = s.get("device_name")
            action = s.get("action")
            if esp is None or dev is None or name is None or action is None:
                errs.append(error(f"{tc_id}: state_setup[{i}] missing required fields"))
                continue
            if not isinstance(esp, int) or esp < 0:
                errs.append(error(f"{tc_id}: state_setup[{i}].espID must be non-negative int"))
            if dev not in ("actuator", "sensor"):
                errs.append(error(f"{tc_id}: state_setup[{i}].device_type must be 'actuator' or 'sensor'"))
            if not isinstance(name, str):
                errs.append(error(f"{tc_id}: state_setup[{i}].device_name must be string"))
            # rule: state_setup should only include actuator initializations with action 'set'
            if dev != "actuator":
                errs.append(error(f"{tc_id}: state_setup[{i}] must be actuator per rules"))
            if action != "set":
                errs.append(error(f"{tc_id}: state_setup[{i}].action must be 'set' per rules"))

    return errs


def validate_deterministic(det: Dict[str, Any], tc_id: str) -> List[str]:
    errs: List[str] = []
    if not isinstance(det, dict):
        return [error(f"{tc_id}: deterministic_eval must be an object")]

    for key in ("must_check_note", "must_check_schedule"):
        if key not in det or not isinstance(det[key], bool):
            errs.append(error(f"{tc_id}: deterministic_eval.{key} must be boolean"))

    ex = det.get("expected_state")
    if ex is None or not isinstance(ex, list):
        errs.append(error(f"{tc_id}: deterministic_eval.expected_state must be a list"))
    else:
        for i, e in enumerate(ex):
            if not isinstance(e, dict):
                errs.append(error(f"{tc_id}: expected_state[{i}] must be object"))
                continue
            esp = e.get("espID")
            dev = e.get("device_type")
            name = e.get("device_name")
            if esp is None or dev is None or name is None or "value" not in e:
                errs.append(error(f"{tc_id}: expected_state[{i}] missing required keys"))
                continue
            if not isinstance(esp, int) or esp < 0:
                errs.append(error(f"{tc_id}: expected_state[{i}].espID must be non-negative int"))
            if dev not in ("actuator", "sensor"):
                errs.append(error(f"{tc_id}: expected_state[{i}].device_type must be 'actuator' or 'sensor'"))

    for list_key in ("required_tool_calls", "abandon_tool_calls"):
        v = det.get(list_key)
        if v is None:
            errs.append(error(f"{tc_id}: deterministic_eval.{list_key} missing"))
        elif not isinstance(v, list):
            errs.append(error(f"{tc_id}: deterministic_eval.{list_key} must be list"))
        else:
            for i, it in enumerate(v):
                if not isinstance(it, str):
                    errs.append(error(f"{tc_id}: {list_key}[{i}] must be string tool name"))

    for ap_key in ("required_appliances", "abandon_appliance"):
        v = det.get(ap_key)
        if v is None:
            errs.append(error(f"{tc_id}: deterministic_eval.{ap_key} missing"))
        elif not isinstance(v, list):
            errs.append(error(f"{tc_id}: deterministic_eval.{ap_key} must be list"))
        else:
            for i, a in enumerate(v):
                if not isinstance(a, dict):
                    errs.append(error(f"{tc_id}: {ap_key}[{i}] must be object"))
                    continue
                esp = a.get("espID")
                dev = a.get("device_type")
                name = a.get("device_name")
                act = a.get("action")
                if esp is None or dev is None or name is None or act is None:
                    errs.append(error(f"{tc_id}: {ap_key}[{i}] missing keys"))
                    continue
                if not isinstance(esp, int) or esp < 0:
                    errs.append(error(f"{tc_id}: {ap_key}[{i}].espID must be non-negative int"))
                if dev not in ("actuator", "sensor"):
                    errs.append(error(f"{tc_id}: {ap_key}[{i}].device_type must be 'actuator' or 'sensor'"))
                if act not in ("get", "set"):
                    errs.append(error(f"{tc_id}: {ap_key}[{i}].action must be 'get' or 'set'"))

    oc = det.get("ordering_constraints")
    if oc is None or not isinstance(oc, list):
        errs.append(error(f"{tc_id}: deterministic_eval.ordering_constraints must be list"))
    else:
        for i, seq in enumerate(oc):
            if not isinstance(seq, list) or not all(isinstance(x, str) for x in seq):
                errs.append(error(f"{tc_id}: ordering_constraints[{i}] must be list of tool-name strings"))

    return errs


def validate_llm_judge(j: Dict[str, Any], tc_id: str) -> List[str]:
    errs: List[str] = []
    if not isinstance(j, dict):
        return [error(f"{tc_id}: llm_judge_eval must be object")]

    for key in ("judge_focus", "required_behaviors", "acceptable_behaviors", "forbidden_behaviors"):
        v = j.get(key)
        if v is None or not isinstance(v, list):
            errs.append(error(f"{tc_id}: llm_judge_eval.{key} must be list"))

    rr = j.get("response_requirements")
    if rr is None or not isinstance(rr, dict):
        errs.append(error(f"{tc_id}: llm_judge_eval.response_requirements must be object"))
    else:
        for k in ("must_confirm_result", "must_explain_if_not_executed", "must_be_consistent_with_environment_change", "must_not_overclaim"):
            if k not in rr or not isinstance(rr[k], bool):
                errs.append(error(f"{tc_id}: response_requirements.{k} must be boolean"))

    traj = j.get("trajectory_judgment")
    if traj is None or not isinstance(traj, dict):
        errs.append(error(f"{tc_id}: llm_judge_eval.trajectory_judgment must be object"))
    else:
        for pat_key in ("required_step_patterns", "preferred_step_patterns", "forbidden_step_patterns"):
            v = traj.get(pat_key)
            if v is None or not isinstance(v, list):
                errs.append(error(f"{tc_id}: trajectory_judgment.{pat_key} must be list"))
            else:
                for i, p in enumerate(v):
                    if not isinstance(p, dict):
                        errs.append(error(f"{tc_id}: trajectory_judgment.{pat_key}[{i}] must be object"))
                        continue
                    if "actor" not in p or "action" not in p or "tool" not in p:
                        errs.append(error(f"{tc_id}: trajectory_judgment.{pat_key}[{i}] must include actor, action, tool"))

        ref = traj.get("reference_flow")
        if ref is None or not isinstance(ref, list):
            errs.append(error(f"{tc_id}: trajectory_judgment.reference_flow must be list"))
        else:
            for i, r in enumerate(ref):
                if not isinstance(r, dict):
                    errs.append(error(f"{tc_id}: reference_flow[{i}] must be object"))
                else:
                    if "actor" not in r or "action" not in r:
                        errs.append(error(f"{tc_id}: reference_flow[{i}] must include actor and action"))

    if not isinstance(j.get("judge_note", ""), str):
        errs.append(error(f"{tc_id}: llm_judge_eval.judge_note must be string"))

    return errs


def validate_testcase(tc: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    tc_id = tc.get("id", "<no-id>")
    if "id" not in tc or not isinstance(tc["id"], str):
        errs.append(error(f"{tc_id}: missing or invalid 'id'"))
    if "task_type" not in tc or not isinstance(tc["task_type"], str):
        errs.append(error(f"{tc_id}: missing or invalid 'task_type'"))
    if "prompt" not in tc or not isinstance(tc["prompt"], str):
        errs.append(error(f"{tc_id}: missing or invalid 'prompt'"))

    pre = tc.get("preconditions")
    if pre is None:
        errs.append(error(f"{tc_id}: missing preconditions"))
    else:
        errs.extend(validate_preconditions(pre, tc_id))

    det = tc.get("deterministic_eval")
    if det is None:
        errs.append(error(f"{tc_id}: missing deterministic_eval"))
    else:
        errs.extend(validate_deterministic(det, tc_id))

    j = tc.get("llm_judge_eval")
    if j is None:
        errs.append(error(f"{tc_id}: missing llm_judge_eval"))
    else:
        errs.extend(validate_llm_judge(j, tc_id))

    return errs


def main():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("part_28_tc726-tc750.json")
    if not p.exists():
        print(f"Dataset not found: {p}")
        sys.exit(2)
    try:
        cases = load_dataset(p)
    except Exception as e:
        print(f"Failed to load dataset: {e}")
        sys.exit(2)

    total = 0
    total_errs = 0
    for tc in cases:
        total += 1
        errs = validate_testcase(tc)
        if errs:
            total_errs += len(errs)
            print(f"--- {tc.get('id','<no-id>')} errors ({len(errs)}):")
            for e in errs:
                print(" -", e)

    if total_errs:
        print(f"Validation finished: {total_errs} error(s) in {total} testcase(s)")
        sys.exit(1)
    print(f"Validation finished: all {total} testcases passed structural checks")
    sys.exit(0)


if __name__ == "__main__":
    main()
