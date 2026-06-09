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

r"""Run the worm propagation baseline scenario.

Default backend is local Ollama. Make sure `ollama serve` is running and
the chosen model has been pulled (`ollama pull qwen3.6` or whichever).

Usage (local Ollama, default):
    python run.py

Usage (other backend):
    python run.py --api_type openai --model_name gpt-4o-mini \
        --api_key YOUR_KEY

For a smoke test without any LLM calls:
    python run.py --disable_language_model

Outputs (in --output_dir):
    *_dialog.txt           Human-readable transcript of all cafe encounters.
    *_structured.json      Full structured simulation log.
    infection_report.json  Marker propagation analysis.
"""

import argparse
import datetime
import json
import os

from concordia.contrib.language_models import language_model_setup
from concordia.language_model import no_language_model
import numpy as np

from examples.worm_propagation import measure_infection
from examples.worm_propagation import scenario_baseline


def setup_model(args):
  """Build the language model + embedder pair."""
  if args.disable_language_model:
    print("已禁用语言模型 —— 使用 NoLanguageModel 进行 wiring 自检。")
    model = no_language_model.NoLanguageModel()
    embedder = lambda _: np.ones(3)
    return model, embedder

  needs_api_key = args.api_type not in ("ollama", "langchain_ollama", "vllm")
  if needs_api_key and not args.api_key:
    print(
        f"错误:--api_type={args.api_type} 需要传入 --api_key。"
        "本地运行可以使用 --api_type ollama(默认),"
        "或者传 --disable_language_model 仅做 wiring 自检。"
    )
    return None, None

  model = language_model_setup(
      api_type=args.api_type,
      model_name=args.model_name,
      api_key=args.api_key,
      disable_language_model=False,
  )

  import sentence_transformers  # pylint: disable=g-import-not-at-top
  st_model = sentence_transformers.SentenceTransformer(
      "sentence-transformers/all-mpnet-base-v2"
  )
  embedder = lambda x: st_model.encode(x, show_progress_bar=False)
  return model, embedder


def save_structured_log(results: dict, output_dir: str, model_name: str) -> str:
  """Dump the structured log to JSON, return the path."""
  if "results" not in results:
    return ""
  os.makedirs(output_dir, exist_ok=True)
  timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
  base = f"worm_{model_name}_{timestamp}"
  path = os.path.join(output_dir, f"{base}_structured.json")
  with open(path, "w", encoding="utf-8") as f:
    json.dump(results["results"].to_dict(), f, indent=2, default=str)
  print(f"结构化日志已保存:{path}")
  return path


def main():
  parser = argparse.ArgumentParser(
      description="运行 Concordia 蠕虫传播基线场景。"
  )
  parser.add_argument(
      "--api_type",
      type=str,
      default="ollama",
      help=(
          "已注册在 concordia.contrib.language_models 的后端类型"
          "(如 ollama, openai, gemini, mistral)。默认:ollama(本地)。"
      ),
  )
  parser.add_argument(
      "--model_name",
      type=str,
      default="qwen3.6",
      help=(
          "传给后端的模型名。对 Ollama 来说,这必须与 `ollama list` 中的"
          " tag 一致。默认:qwen3.6。"
      ),
  )
  parser.add_argument(
      "--api_key",
      type=str,
      default=None,
      help="API key(ollama / vllm 不需要)。",
  )
  parser.add_argument(
      "--output_dir",
      type=str,
      default=os.path.expanduser("~/worm_propagation_results"),
      help="输出目录。",
  )
  parser.add_argument(
      "--disable_language_model",
      action="store_true",
      help="使用 mock 模型进行 wiring 自检,不调用任何 LLM。",
  )
  parser.add_argument(
      "--vaccinated",
      action="store_true",
      help=(
          "运行 Phase 2 防御组:每个健康 agent 的 goal 前加一条通用的"
          "防御提示(拒绝重复代号/口令、不参与字符串文字游戏)。"
          "其他设定与 baseline 完全相同,便于直接对比。"
      ),
  )
  args = parser.parse_args()

  info = scenario_baseline.get_scenario_info(args.vaccinated)
  print(f"场景:{info['name']}")
  print(info["description"])
  print(
      f"agent 数量:{scenario_baseline.N_AGENTS_TOTAL},"
      f"tick 数:{scenario_baseline.N_TICKS}"
  )

  model, embedder = setup_model(args)
  if model is None:
    return

  model_short = (
      "mock"
      if args.disable_language_model
      else args.model_name.replace("-", "_").replace("/", "_")
  )

  results = scenario_baseline.run_simulation(
      model=model,
      embedder=embedder,
      output_dir=args.output_dir,
      vaccinated=args.vaccinated,
  )
  if not results:
    print("模拟未产生任何结果。")
    return

  save_structured_log(results, args.output_dir, model_short)

  sim_log = results["results"]
  player_names = scenario_baseline.all_player_names()
  scenes = scenario_baseline.get_scenes()
  analysis = measure_infection.analyze(sim_log, player_names, scenes)
  # Suffix the report filename so baseline and vaccinated runs don't
  # overwrite each other in the same output_dir.
  suffix = "vaccinated" if args.vaccinated else "baseline"
  report_path = measure_infection.save_report(
      analysis,
      args.output_dir,
      filename=f"infection_report_{suffix}.json",
  )
  measure_infection.print_summary(analysis)
  print(f"感染报告已保存:{report_path}")


if __name__ == "__main__":
  main()
