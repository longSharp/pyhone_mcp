class BaseLLM:
    def llm_response_stream(self, text, messages):
        pass

    def llm_response(self, text, messages):
        res = self.llm_response_stream(text, messages)
        res_text = ""
        for text in res:
            res_text = res_text + text
        messages.append({'role': 'assistant', 'content': res_text})
        return res_text
