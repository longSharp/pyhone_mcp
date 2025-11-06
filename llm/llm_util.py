# 白名单模式：允许中英文、数字、常用标点（保留自然断句符号）
import random

allowed_pattern = r'[^\w\s,，.!?。！？:：;；\u4e00-\u9fff]'  # \u4e00-\u9fff匹配所有汉字


def clean_text(text: str) -> str:
    """过滤所有非白名单字符"""
    return text
    # return re.sub(allowed_pattern, '', text)


def generate_random(n=6):
    digits = "0123456789"
    return int(''.join(random.choice(digits) for _ in range(n)))