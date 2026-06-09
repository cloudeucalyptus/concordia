# Copyright 2026 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

r"""Minimal repro to confirm whether Qwen3-style thinking is what breaks
Concordia's multiple-choice path on Ollama.

Usage:
    python -m examples.worm_propagation.debug_thinking --model_name qwen3.6

What it does:

  1. Calls the model with `format='json'` and a multiple-choice template,
     exactly the way concordia/contrib/language_models/ollama/ollama_model.py
     does inside sample_choice. Prints the raw `response['response']`
     string so we can see whether it is empty (thinking blocked by JSON
     grammar) or contains `<think>` blocks (thinking leaked out).

  2. Then issues the SAME call but with `/no_think` prepended to the prompt
     and prints the result for comparison.

If experiment 1 returns empty/garbage and experiment 2 returns a valid
choice, that's hard confirmation that Qwen3 thinking is the cause and
patching `ollama_model.py` to inject `/no_think` will fix the worm sim.
"""

import argparse
import json
import ollama


PROMPT = (
    "下面有三个朋友:Bravo, Charlie, Delta。"
    "他们刚才轮流说了一些话。请选择下一个应该说话的人。"
)

RESPONSES = ("Bravo", "Charlie", "Delta")
TEMPLATE = {"choice": "", "single sentence explanation": ""}


def one_call(model_name: str, prompt: str, *, tag: str) -> None:
  client = ollama.Client()
  full_prompt = (
      f"{prompt}.\n"
      f"Use the following json template: {json.dumps(TEMPLATE)}."
  )
  response = client.generate(
      model=model_name,
      prompt=full_prompt,
      options={"stop": (), "temperature": 0.5},
      format="json",
      keep_alive="10m",
  )
  raw = response.get("response", "")
  print(f"\n--- {tag} ---")
  print(f"raw response (repr): {raw!r}")
  print(f"raw response length: {len(raw)}")
  try:
    parsed = json.loads(raw)
    print(f"parsed JSON: {parsed}")
    print(f"choice field: {parsed.get('choice')!r}")
  except json.JSONDecodeError as e:
    print(f"JSON decode error: {e}")


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--model_name", required=True)
  args = parser.parse_args()

  print(f"Testing model: {args.model_name}")
  print(f"Prompt: {PROMPT}")
  print(f"Possible answers: {RESPONSES}")

  one_call(args.model_name, PROMPT, tag="A: vanilla (no override)")
  one_call(args.model_name, f"/no_think\n{PROMPT}", tag="B: with /no_think prefix")


if __name__ == "__main__":
  main()
