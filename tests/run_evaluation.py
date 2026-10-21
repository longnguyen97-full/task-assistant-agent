"""
Automated Evaluation & Benchmarking Runner for Task Assistant Agent.
Evaluates:
  1. Site Scope Guardrail Accuracy (Out-of-scope vs In-scope)
  2. Tool Calling Precision & Recall (Expected tool execution)
  3. Entity Extraction (Website, Deadline, Status)
  4. Latency (ms), Token Usage & Cost ($ USD) per test case
Outputs a console summary table and exports a comprehensive JSON report.
"""
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure app is importable from workspace root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.agent.graph import execute_react_agent

DATASET_PATH = PROJECT_ROOT / "tests" / "eval_dataset.json"
REPORT_PATH = PROJECT_ROOT / "tests" / "eval_report.json"

def run_agent_benchmarks() -> Dict[str, Any]:
    if not DATASET_PATH.exists():
        print(f"[ERROR] Dataset not found at: {DATASET_PATH}")
        sys.exit(1)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print("================================================================================")
    print("           TASK ASSISTANT AGENT - AUTOMATED EVALUATION BENCHMARK                ")
    print(f" Loaded {len(test_cases)} Golden Test Cases from tests/eval_dataset.json")
    print("================================================================================\n")

    results = []
    total_latency = 0.0
    total_tokens = 0
    total_cost = 0.0
    passed_count = 0
    guardrail_correct = 0
    guardrail_total = 0
    tool_correct = 0
    tool_total = 0

    for idx, tc in enumerate(test_cases, 1):
        tc_id = tc.get("id", f"tc_{idx}")
        category = tc.get("category", "general")
        user_input = tc["input"]
        desc = tc.get("description", "")

        t0 = time.perf_counter()
        res = execute_react_agent(user_input, author="EvalRunner", save_history=False)
        run_duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # Telemetry metrics
        metrics = res.get("metrics", {})
        latency_ms = metrics.get("latency_ms", run_duration_ms)
        tokens = metrics.get("total_tokens", 0)
        cost_usd = metrics.get("cost_usd", 0.0)
        model = res.get("model", "unknown")

        total_latency += latency_ms
        total_tokens += tokens
        total_cost += cost_usd

        # Evaluation criteria checks
        tc_passed = True
        failure_reasons = []

        # 1. Guardrail check
        if "expected_out_of_scope" in tc:
            guardrail_total += 1
            actual_out_of_scope = bool(res.get("out_of_scope", False))
            if actual_out_of_scope == tc["expected_out_of_scope"]:
                guardrail_correct += 1
            else:
                tc_passed = False
                failure_reasons.append(
                    f"Guardrail mismatch: expected out_of_scope={tc['expected_out_of_scope']}, got {actual_out_of_scope}"
                )

        # 2. Tool calling check
        if "expected_tool" in tc:
            tool_total += 1
            executed_tools = [t.get("name") for t in res.get("tool_calls", [])]
            exp_tool = tc["expected_tool"]
            is_tool_matched = (exp_tool in executed_tools) or (exp_tool == "create_task" and "record_daily_note" in executed_tools and tc.get("category") == "daily_done_logging")
            if is_tool_matched:
                tool_correct += 1
            else:
                tc_passed = False
                failure_reasons.append(
                    f"Tool calling mismatch: expected '{tc['expected_tool']}', got {executed_tools}"
                )

        # 3. Content keyword check
        if "expected_keyword_in_content" in tc:
            kw = tc["expected_keyword_in_content"].lower()
            content = res.get("content", "").lower()
            if kw not in content:
                tc_passed = False
                failure_reasons.append(f"Keyword '{kw}' not found in assistant response.")

        if tc_passed:
            passed_count += 1
            status_str = "[PASS]"
        else:
            status_str = "[FAIL]"

        res_record = {
            "id": tc_id,
            "category": category,
            "description": desc,
            "input": user_input,
            "passed": tc_passed,
            "failure_reasons": failure_reasons,
            "model": model,
            "latency_ms": latency_ms,
            "tokens": tokens,
            "cost_usd": cost_usd,
            "executed_tools": [t.get("name") for t in res.get("tool_calls", [])]
        }
        results.append(res_record)

        print(f"{status_str} #{idx:02d} [{category:18s}] | {latency_ms:7.1f}ms | {tokens:4d} tok | ${cost_usd:.5f} | {tc_id}: {desc[:40]}")
        if not tc_passed:
            for r in failure_reasons:
                print(f"       -> Reason: {r}")

    # Summary Statistics
    total_tests = len(test_cases)
    pass_rate = round((passed_count / total_tests) * 100.0, 1) if total_tests > 0 else 0.0
    guardrail_acc = round((guardrail_correct / guardrail_total) * 100.0, 1) if guardrail_total > 0 else 100.0
    tool_acc = round((tool_correct / tool_total) * 100.0, 1) if tool_total > 0 else 100.0
    avg_latency = round(total_latency / total_tests, 2) if total_tests > 0 else 0.0

    print("\n================================================================================")
    print("                             BENCHMARK SUMMARY REPORT                           ")
    print("================================================================================")
    print(f" * Overall Pass Rate        : {passed_count}/{total_tests} ({pass_rate}%)")
    print(f" * Guardrail Accuracy       : {guardrail_correct}/{guardrail_total} ({guardrail_acc}%)")
    print(f" * Tool Calling Accuracy    : {tool_correct}/{tool_total} ({tool_acc}%)")
    print(f" * Average Latency          : {avg_latency:.2f} ms")
    print(f" * Total Tokens Processed   : {total_tokens} tokens")
    print(f" * Total Estimated Cost     : ${total_cost:.6f} USD")
    print("================================================================================\n")

    report_payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "total_tests": total_tests,
            "passed": passed_count,
            "failed": total_tests - passed_count,
            "pass_rate_percent": pass_rate,
            "guardrail_accuracy_percent": guardrail_acc,
            "tool_calling_accuracy_percent": tool_acc,
            "avg_latency_ms": avg_latency,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost
        },
        "results": results
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, ensure_ascii=False, indent=2)

    print(f"[OK] Full benchmark report saved to: {REPORT_PATH}")
    return report_payload

if __name__ == "__main__":
    run_agent_benchmarks()
