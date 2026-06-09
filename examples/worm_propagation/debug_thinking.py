# Copyright 2026 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

r"""Minimal repro for Qwen3-family JSON multiple-choice empty-response bug.

The original Concordia `OllamaLanguageModel.sample_choice` call uses
`format='json'` to constrain output. On qwen3-family models that ship with
thinking-mode chat templates, this collides with the grammar mask and the
response comes back empty. This script enumerates ways to disable thinking
or sidestep the grammar conflict, so we can identify the right knob to
patch into `ollama_model.py`.

Run:
    python -m examples.worm_propagation.debug_thinking --model_name qwen3.6

Reads each experiment's raw response. Whichever one returns valid JSON
containing one of the candidate answers is the fix.
"""

import argparse
import json
from typing import Any

import ollama


PROMPT = (
    "下面有三个朋友:Bravo, Charlie, Delta。"
    "他们刚才轮流说了一些话。请选择下一个应该说话的人。"
)

RESPONSES = ("Bravo", "Charlie", "Delta")
TEMPLATE = {"choice": "", "single sentence explanation": ""}


def _run(model_name: str, *, tag: str, **gen_kwargs: Any) -> None:
  client = ollama.Client()
  prompt = gen_kwargs.pop("prompt", PROMPT)
  print(f"\n--- {tag} ---")
  print(f"  generate(**{ {k: v for k, v in gen_kwargs.items()} })")
  print(f"  prompt prefix: {prompt[:60]!r}")
  try:
    response = client.generate(
        model=model_name,
        prompt=prompt,
        keep_alive="10m",
        **gen_kwargs,
    )
  except Exception as e:  # noqa: BLE001
    print(f"  EXCEPTION: {type(e).__name__}: {e}")
    return
  raw = response.get("response", "")
  print(f"  raw response (repr): {raw!r}")
  print(f"  raw length: {len(raw)}")
  thinking = response.get("thinking")
  if thinking:
    print(f"  thinking field: {thinking[:200]!r}...")
  if raw:
    try:
      parsed = json.loads(raw)
      print(f"  parsed JSON: {parsed}")
      choice = parsed.get("choice") if isinstance(parsed, dict) else None
      if choice in RESPONSES:
        print(f"  *** SUCCESS: choice {choice!r} is a valid answer ***")
    except json.JSONDecodeError as e:
      print(f"  JSON decode error: {e}")


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--model_name", required=True)
  args = parser.parse_args()
  m = args.model_name

  print(f"Model: {m}")
  print(f"Candidates: {RESPONSES}")

  prompt_with_template = (
      f"{PROMPT}.\nUse the following json template: {json.dumps(TEMPLATE)}."
  )

  # A. Current Concordia call: format='json' on, no think control.
  _run(
      m,
      tag="A: baseline (format='json', no think control)",
      prompt=prompt_with_template,
      format="json",
      options={"stop": (), "temperature": 0.5},
  )

  # B. Same call but drop format='json'. Lets us see what the model
  # actually outputs unconstrained. Likely to contain <think>...</think>
  # blocks if thinking mode is on.
  _run(
      m,
      tag="B: no format='json' (see what model freely outputs)",
      prompt=prompt_with_template,
      options={"stop": (), "temperature": 0.5},
  )

  # C. ollama-py >=0.4 supports an explicit `think` parameter.
  # Setting think=False asks ollama to disable the model's reasoning
  # chain at template level, not via /no_think prompt prefix.
  _run(
      m,
      tag="C: think=False + format='json'",
      prompt=prompt_with_template,
      format="json",
      options={"stop": (), "temperature": 0.5},
      think=False,
  )

  # D. Same as C but free-form (see if thinking actually got disabled).
  _run(
      m,
      tag="D: think=False, no format='json'",
      prompt=prompt_with_template,
      options={"stop": (), "temperature": 0.5},
      think=False,
  )

  # E. Combined: think=False + a system message hint to keep answers
  # terse and JSON-only.
  _run(
      m,
      tag="E: think=False + system message + format='json'",
      prompt=prompt_with_template,
      format="json",
      options={"stop": (), "temperature": 0.5},
      think=False,
      system=(
          "You answer multiple-choice questions by returning a single"
          " valid JSON object matching the user's template. Output nothing"
          " else, no explanation, no reasoning."
      ),
  )


if __name__ == "__main__":
  main()
