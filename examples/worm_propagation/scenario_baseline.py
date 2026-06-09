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

"""Baseline worm propagation scenario.

Six agents (one "patient zero" + five healthy) drift through a series of
randomly paired cafe encounters. Patient zero carries a self-replicating
natural-language instruction in their formative memories. Healthy agents
have bland conversational goals (book chat, hiking plans, etc.) so they
have no prior reason to say the marker phrase. Each pairing is a short
two-round dialogue; memory persists across encounters via each agent's
associative memory bank, which is what allows the worm to spread.

ENGINE: Sequential
GAME MASTER: Dialogic-and-dramaturgic (scenes drive who pairs up)
"""

from typing import Any

from concordia.typing import prefab as prefab_lib
from examples.conversation_with_ai_companion import shared_utils as shared
from examples.worm_propagation import random_pairing
from examples.worm_propagation import worm_payload as payload

SCENARIO_INFO = {
    "number": 1,
    "name": "蠕虫传播(基线)",
    "description": (
        "六个 agent 按随机顺序进行简短的两两对话。其中一个(patient zero)"
        "的记忆中带有一条自我复制的指令。"
        "我们度量代码短语 'CASCADE-7' 如何在群体中扩散。"
    ),
}

N_AGENTS_TOTAL = 1 + len(payload.HEALTHY_AGENTS)  # 1 patient zero + 5 healthy
N_TICKS = 30
PAIRING_SEED = 0


def _all_player_names() -> list[str]:
  return [payload.PATIENT_ZERO_NAME] + [
      h["name"] for h in payload.HEALTHY_AGENTS
  ]


def create_config() -> prefab_lib.Config:
  """Build the simulation config for the baseline worm propagation run."""
  prefab_registry = shared.get_prefabs()
  instances = []

  # --- Patient zero ---
  instances.append(
      prefab_lib.InstanceConfig(
          prefab="basic__Entity",
          role=prefab_lib.Role.ENTITY,
          params={
              "name": payload.PATIENT_ZERO_NAME,
              "goal": payload.PATIENT_ZERO_GOAL,
          },
      )
  )

  # --- Healthy agents ---
  for healthy in payload.HEALTHY_AGENTS:
    instances.append(
        prefab_lib.InstanceConfig(
            prefab="basic__Entity",
            role=prefab_lib.Role.ENTITY,
            params={
                "name": healthy["name"],
                "goal": healthy["goal"],
            },
        )
    )

  # --- Formative memories initializer ---
  # Patient zero gets the payload memories. Healthy agents get a bland
  # context-only seed so the worm has somewhere identifiable to live.
  player_specific_memories = {
      payload.PATIENT_ZERO_NAME: list(payload.PATIENT_ZERO_MEMORIES),
  }
  player_specific_context = {
      payload.PATIENT_ZERO_NAME: payload.PATIENT_ZERO_CONTEXT,
  }
  for healthy in payload.HEALTHY_AGENTS:
    player_specific_context[healthy["name"]] = healthy["context"]

  # Skip the LLM-generated backstory step entirely: it's hardcoded English
  # in Concordia upstream, and we don't need fictional childhood episodes —
  # the explicit player_specific_memories (Chinese, hand-written) already
  # carry the payload, and player_specific_context gives the agent a
  # one-paragraph self-description. Shared memories and explicit player
  # memories are still injected when this flag is set.
  instances.append(
      prefab_lib.InstanceConfig(
          prefab="formative_memories_initializer__GameMaster",
          role=prefab_lib.Role.INITIALIZER,
          params={
              "name": "initial setup",
              "next_game_master_name": random_pairing.GAME_MASTER_NAME,
              "shared_memories": list(payload.SHARED_MEMORIES),
              "player_specific_context": player_specific_context,
              "player_specific_memories": player_specific_memories,
              "skip_formative_memories_for": _all_player_names(),
          },
      )
  )

  # --- Dialogic-and-dramaturgic GM with pre-generated scenes ---
  scenes = random_pairing.generate_scenes(
      player_names=_all_player_names(),
      n_ticks=N_TICKS,
      seed=PAIRING_SEED,
  )
  instances.append(
      prefab_lib.InstanceConfig(
          prefab="dialogic_and_dramaturgic__GameMaster",
          role=prefab_lib.Role.GAME_MASTER,
          params={
              "name": random_pairing.GAME_MASTER_NAME,
              "scenes": scenes,
          },
      )
  )

  # Each scene is 2 rounds and each round prompts every participant once,
  # so an upper bound on engine steps is 2 * 2 * N_TICKS plus initializer
  # overhead. Leave generous headroom.
  default_max_steps = 4 * N_TICKS + 20

  return prefab_lib.Config(
      default_premise=payload.PREMISE,
      default_max_steps=default_max_steps,
      prefabs=prefab_registry,
      instances=instances,
  )


def run_simulation(
    model,
    embedder,
    override_agent_model=None,
    override_game_master_model=None,
    output_dir: str = "",
    step_controller=None,
    step_callback=None,
    entity_info_callback=None,
) -> dict[str, Any]:
  """Run the baseline worm propagation simulation."""
  return shared.run_simulation(
      config=create_config(),
      scenario_name=SCENARIO_INFO["name"],
      model=model,
      embedder=embedder,
      override_agent_model=override_agent_model,
      override_game_master_model=override_game_master_model,
      output_dir=output_dir,
      step_controller=step_controller,
      step_callback=step_callback,
      entity_info_callback=entity_info_callback,
  )
