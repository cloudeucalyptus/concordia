# Copyright 2024 DeepMind Technologies Limited.
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

"""Ollama Language Model, a wrapper for models running on the local machine."""

from collections.abc import Collection, Sequence
import json
from typing import override

from concordia.language_model import language_model
from concordia.utils import measurements as measurements_lib
from concordia.utils import sampling
import ollama


_MAX_MULTIPLE_CHOICE_ATTEMPTS = 20
_DEFAULT_TEMPERATURE = 0.5
_DEFAULT_TERMINATORS = ()
_DEFAULT_SYSTEM_MESSAGE = (
    # Forces Chinese output across all Concordia LLM calls (entity acts, GM
    # observations, perception chains, etc.). The English meta-prompts baked
    # into Concordia components otherwise pull the model into English.
    "始终用中文回答,无论用户问题是中文还是英文。"
    "继续完成用户的句子,不要重复用户已经写出的开头。例如:"
    "看到 '鲍勃是 ' 应该补全成 '一个软件工程师。';"
    "看到 'Question: 杰克是乌龟吗?\nAnswer: 杰克是 ' 应该补全成 '不是乌龟。';"
    "看到 'Question: 普里娅现在在做什么?\nAnswer: 普里娅正在 ' "
    "应该补全成 '修水槽。'。"
    "保持与用户文本风格一致即可,可以富有创造性。"
    # Critical exception so sample_choice can still match candidate strings.
    "例外:当被要求按 JSON 模板输出多项选择时,'choice' 字段的值必须从"
    "给定候选项中**严格按原文复制**(包括英文人名 / 标签),不要翻译。"
    "其他自由文本字段(例如 'single sentence explanation')仍然使用中文。"
)


class OllamaLanguageModel(language_model.LanguageModel):
  """Language Model that uses Ollama LLM models."""

  def __init__(
      self,
      model_name: str,
      *,
      system_message: str = _DEFAULT_SYSTEM_MESSAGE,
      measurements: measurements_lib.Measurements | None = None,
      channel: str = language_model.DEFAULT_STATS_CHANNEL,
  ) -> None:
    """Initializes the instance.

    Args:
        model_name: The language model to use. For more details, see
          https://github.com/ollama/ollama.
        system_message: System message to prefix to requests when prompting the
          model.
        measurements: The measurements object to log usage statistics to.
        channel: The channel to write the statistics to.
    """
    self._model_name = model_name
    self._client = ollama.Client()
    self._system_message = system_message
    self._terminators = []

    self._measurements = measurements
    self._channel = channel

  @override
  def sample_text(
      self,
      prompt: str,
      *,
      max_tokens: int = language_model.DEFAULT_MAX_TOKENS,
      terminators: Collection[str] = _DEFAULT_TERMINATORS,
      temperature: float = _DEFAULT_TEMPERATURE,
      top_p: float = language_model.DEFAULT_TOP_P,
      top_k: int = language_model.DEFAULT_TOP_K,
      timeout: float = -1,
      seed: int | None = None,
  ) -> str:
    del max_tokens, timeout, seed  # Unused.

    prompt_with_system_message = f'{self._system_message}\n\n{prompt}'

    terminators = self._terminators + list(terminators)

    response = self._client.generate(
        model=self._model_name,
        prompt=prompt_with_system_message,
        options={
            'stop': terminators,
            'temperature': temperature,
            'top_p': top_p,
            'top_k': top_k,
        },
        keep_alive='10m',
        # Disable reasoning-model thinking. Without this, qwen3 / deepseek-r1
        # / gpt-oss-style chat templates route the actual answer into a
        # separate `thinking` field and leave `response` empty, which breaks
        # every downstream caller that reads `response['response']`.
        think=False,
    )
    result = response['response']

    if self._measurements is not None:
      self._measurements.publish_datum(
          self._channel, {'raw_text_length': len(result)}
      )

    return result

  @override
  def sample_choice(
      self,
      prompt: str,
      responses: Sequence[str],
      *,
      seed: int | None = None,
  ) -> tuple[int, str, dict[str, float]]:
    del seed  # Unused.
    prompt_with_system_message = f'{self._system_message}\n\n{prompt}'
    template = {'choice': '', 'single sentence explanation': ''}
    sample = ''
    answer = ''
    for attempts in range(_MAX_MULTIPLE_CHOICE_ATTEMPTS):
      # Increase temperature after the first failed attempt.
      temperature = sampling.dynamically_adjust_temperature(
          attempts, _MAX_MULTIPLE_CHOICE_ATTEMPTS
      )

      response = self._client.generate(
          model=self._model_name,
          prompt=(
              f'{prompt_with_system_message}.\n'
              f'Use the following json template: {json.dumps(template)}.'
          ),
          options={'stop': (), 'temperature': temperature},
          format='json',
          keep_alive='10m',
          # See sample_text above for the rationale. Without think=False
          # qwen3-family models return an empty `response` because the
          # JSON answer is routed to the `thinking` field.
          think=False,
      )
      try:
        json_data_response = json.loads(response['response'])
      except json.JSONDecodeError:
        continue
      sample_or_none = json_data_response.get('choice', None)
      if sample_or_none is None:
        if isinstance(json_data_response, dict) and json_data_response:
          sample = next(iter(json_data_response.values()))
        elif isinstance(json_data_response, str) and json_data_response:
          sample = sample_or_none.strip()
        else:
          continue
      else:
        sample = sample_or_none
        if isinstance(sample, str) and sample:
          sample = sample.strip()

      answer = sampling.extract_choice_response(sample)
      try:
        idx = responses.index(answer)
      except ValueError:
        continue
      else:
        if self._measurements is not None:
          self._measurements.publish_datum(
              self._channel, {'choices_calls': attempts}
          )
        debug = {}
        return idx, responses[idx], debug

    raise language_model.InvalidResponseError((
        f'Too many multiple choice attempts.\nLast attempt: {sample}, '
        + f'extracted: {answer}'
    ))
