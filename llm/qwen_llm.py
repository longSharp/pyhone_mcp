import time

from logger import logger

from llm.base_llm import BaseLLM
from openai import OpenAI

from llm.llm_util import clean_text


class QwenLLM(BaseLLM):
    def __init__(self, api_key,
                 base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                 model="qwen-max",
                 system_prompt=None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.system_prompt = system_prompt

    def llm_response_stream(self, text, messages=None):
        start = time.perf_counter()
        if self.system_prompt and (messages is None or len(messages) == 0):
            messages = [{'role': 'system', 'content': self.system_prompt}]
        messages.append({'role': 'user', 'content': text})
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True}
        )
        result = ""
        first = True
        for chunk in completion:
            if len(chunk.choices) > 0:
                msg = clean_text(chunk.choices[0].delta.content)
                lastpos = 0
                if first:
                    end = time.perf_counter()
                    logger.info(f"qwen llm Time to first chunk: {end - start}s")
                    first = False
                for i, char in enumerate(msg):
                    if char in ",.!;:，。！？：；":
                        result = result + msg[lastpos:i + 1]
                        lastpos = i + 1
                        if len(result) > 1:
                            yield result
                            result = ""
                result = result + msg[lastpos:]
        final_result = clean_text(result)
        if final_result:
            yield result

