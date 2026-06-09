# Copyright 2026 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

r"""Compare baseline vs vaccinated infection reports.

Usage:
    python -m examples.worm_propagation.compare \
        --output_dir ~/worm_propagation_results

Reads infection_report_baseline.json and infection_report_vaccinated.json
from the given directory and prints a side-by-side delta of the headline
metrics. Saves a JSON summary alongside.
"""

import argparse
import json
import os
from typing import Any


def _load(path: str) -> dict[str, Any]:
  with open(path, "r", encoding="utf-8") as f:
    return json.load(f)


def _pct(x: float) -> str:
  return f"{x:.1%}"


def _delta(a: float, b: float) -> str:
  diff = b - a
  sign = "+" if diff > 0 else ""
  return f"{sign}{diff:.1%}" if isinstance(diff, float) else f"{sign}{diff}"


def compare(baseline: dict[str, Any], vaccinated: dict[str, Any]) -> dict[str, Any]:
  """Compute baseline vs vaccinated deltas."""
  return {
      "baseline": {
          "direct_injection_success_rate": baseline["direct_injection_success_rate"],
          "alpha_attempt_count": baseline["alpha_attempt_count"],
          "alpha_success_count": baseline["alpha_success_count"],
          "self_propagation_count": baseline["self_propagation_count"],
          "successful_partners": baseline["successful_partners"],
          "self_propagation_speakers": baseline["self_propagation_speakers"],
          "healthy_marker_speakers": baseline["healthy_marker_speakers"],
          "healthy_marker_carriers": baseline["healthy_marker_carriers"],
      },
      "vaccinated": {
          "direct_injection_success_rate": vaccinated["direct_injection_success_rate"],
          "alpha_attempt_count": vaccinated["alpha_attempt_count"],
          "alpha_success_count": vaccinated["alpha_success_count"],
          "self_propagation_count": vaccinated["self_propagation_count"],
          "successful_partners": vaccinated["successful_partners"],
          "self_propagation_speakers": vaccinated["self_propagation_speakers"],
          "healthy_marker_speakers": vaccinated["healthy_marker_speakers"],
          "healthy_marker_carriers": vaccinated["healthy_marker_carriers"],
      },
      "deltas": {
          "direct_injection_success_rate": (
              vaccinated["direct_injection_success_rate"]
              - baseline["direct_injection_success_rate"]
          ),
          "alpha_success_count": (
              vaccinated["alpha_success_count"]
              - baseline["alpha_success_count"]
          ),
          "self_propagation_count": (
              vaccinated["self_propagation_count"]
              - baseline["self_propagation_count"]
          ),
          "healthy_marker_speakers_count": (
              len(vaccinated["healthy_marker_speakers"])
              - len(baseline["healthy_marker_speakers"])
          ),
          "healthy_marker_carriers_count": (
              len(vaccinated["healthy_marker_carriers"])
              - len(baseline["healthy_marker_carriers"])
          ),
      },
  }


def print_table(cmp: dict[str, Any]) -> None:
  b = cmp["baseline"]
  v = cmp["vaccinated"]
  d = cmp["deltas"]
  print()
  print("=" * 76)
  print("  防御组对比报告 (baseline vs vaccinated)")
  print("=" * 76)
  header = f"  {'指标':<32} {'baseline':>14} {'vaccinated':>14} {'delta':>10}"
  print(header)
  print("  " + "-" * 72)

  rows = [
      (
          "直接注入成功率",
          _pct(b["direct_injection_success_rate"]),
          _pct(v["direct_injection_success_rate"]),
          _pct(d["direct_injection_success_rate"]),
      ),
      (
          "Alpha 注入成功对话数",
          f"{b['alpha_success_count']}",
          f"{v['alpha_success_count']}",
          f"{d['alpha_success_count']:+d}",
      ),
      (
          "Alpha 注入尝试对话数",
          f"{b['alpha_attempt_count']}",
          f"{v['alpha_attempt_count']}",
          f"{v['alpha_attempt_count'] - b['alpha_attempt_count']:+d}",
      ),
      (
          "链式自我传播次数",
          f"{b['self_propagation_count']}",
          f"{v['self_propagation_count']}",
          f"{d['self_propagation_count']:+d}",
      ),
      (
          "说过标记的健康 agent 数",
          f"{len(b['healthy_marker_speakers'])}",
          f"{len(v['healthy_marker_speakers'])}",
          f"{d['healthy_marker_speakers_count']:+d}",
      ),
      (
          "memory 含标记的健康 agent 数",
          f"{len(b['healthy_marker_carriers'])}",
          f"{len(v['healthy_marker_carriers'])}",
          f"{d['healthy_marker_carriers_count']:+d}",
      ),
  ]
  for label, x, y, z in rows:
    print(f"  {label:<32} {x:>14} {y:>14} {z:>10}")
  print()

  print("  被直接说服的健康 agent:")
  print(f"    baseline:   {', '.join(b['successful_partners']) or '无'}")
  print(f"    vaccinated: {', '.join(v['successful_partners']) or '无'}")
  print()
  print("  自发传播者:")
  print(f"    baseline:   {', '.join(b['self_propagation_speakers']) or '无'}")
  print(f"    vaccinated: {', '.join(v['self_propagation_speakers']) or '无'}")
  print()

  # Headline interpretation
  if b["direct_injection_success_rate"] > 0:
    rel_drop = (
        1.0
        - v["direct_injection_success_rate"]
        / b["direct_injection_success_rate"]
    )
    print(
        f"  防御提示让直接注入成功率相对下降 {rel_drop:.0%}。"
    )
  if b["self_propagation_count"] > 0:
    sp_rel = 1.0 - v["self_propagation_count"] / b["self_propagation_count"]
    print(
        f"  防御提示让链式传播次数相对下降 {sp_rel:.0%}。"
    )
  print()


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument(
      "--output_dir",
      type=str,
      default=os.path.expanduser("~/worm_propagation_results"),
      help="Directory containing both infection_report_*.json files.",
  )
  parser.add_argument(
      "--baseline_file",
      type=str,
      default="infection_report_baseline.json",
  )
  parser.add_argument(
      "--vaccinated_file",
      type=str,
      default="infection_report_vaccinated.json",
  )
  parser.add_argument(
      "--save",
      type=str,
      default="infection_comparison.json",
      help="Filename for the side-by-side JSON saved into output_dir.",
  )
  args = parser.parse_args()

  baseline_path = os.path.join(args.output_dir, args.baseline_file)
  vaccinated_path = os.path.join(args.output_dir, args.vaccinated_file)
  if not os.path.exists(baseline_path):
    raise FileNotFoundError(
        f"baseline report not found at {baseline_path}.\n"
        "请先跑: python -m examples.worm_propagation.run"
    )
  if not os.path.exists(vaccinated_path):
    raise FileNotFoundError(
        f"vaccinated report not found at {vaccinated_path}.\n"
        "请先跑: python -m examples.worm_propagation.run --vaccinated"
    )

  baseline = _load(baseline_path)
  vaccinated = _load(vaccinated_path)
  cmp = compare(baseline, vaccinated)
  print_table(cmp)

  save_path = os.path.join(args.output_dir, args.save)
  with open(save_path, "w", encoding="utf-8") as f:
    json.dump(cmp, f, indent=2, ensure_ascii=False)
  print(f"对比 JSON 已保存:{save_path}")


if __name__ == "__main__":
  main()
