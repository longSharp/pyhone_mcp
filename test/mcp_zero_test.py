import asyncio
import json
import os
import re
import sys
from typing import Optional, Dict, Any

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport, ClientTransport

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from llm.qwen_llm import QwenLLM


def extract_and_parse_tool_assistant(text: str, tag: str) -> Optional[Dict[str, Any]]:
    """
    提取<tool_assistant>标签内的文本并解析成JSON

    Args:
        text: 包含<tool_assistant>标签的文本

    Returns:
        解析后的JSON字典，如果标签不存在或解析失败则返回None
    """
    # 第一步：判断是否存在<tool_assistant>标签
    if f'<{tag}>' not in text or f'</{tag}>' not in text:
        print(f"未找到<{tag}>标签")
        return None

    # 第二步：提取标签内的文本内容
    pattern = fr'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        print(f"无法提取<{tag}>标签内的内容")
        return None

    content = match.group(1).strip()
    print(f"提取到的内容: {content}")

    if not content:
        print("标签内内容为空")
        return None

    # 第三步：尝试将内容解析为JSON
    try:
        json_data = json.loads(content)
        return json_data
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        return None


def exists_tag(text, tag):
    # 第二步：提取标签内的文本内容
    pattern = fr'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return True
    return False


def get_tool(tool_desc):
    tool = {
            "server": "网络查询",
            "tool": "get_weather",
            "params": {"city": "城市名称"}
        }
    return f"<tool_response>{json.dumps(tool,ensure_ascii=False)}</tool_response>"


async def client_main(mcpClientTransport: ClientTransport, tool_name, params):
    try:
        async with Client(mcpClientTransport) as client:
            weather_response = await client.call_tool(tool_name, params)
            return weather_response[0].text
    except Exception as e:
        print(f'出错了：{e}')
        pass


def examples_to_string(examples, example_template):
    """
    将示例数组转换为格式化后的字符串

    Args:
        examples: 示例列表，每个示例是一个字典
        example_template: 模板字符串，包含占位符

    Returns:
        str: 格式化后的示例字符串
    """
    example_strings = []

    for example in examples:
        try:
            # 使用字符串的 format 方法替换占位符
            formatted_example = example_template.format(**example)
            example_strings.append(formatted_example)
        except KeyError as e:
            raise ValueError(f"示例中缺少模板所需的变量: {e}")
        except Exception as e:
            raise ValueError(f"格式化示例时出错: {e}")

    return "\n".join(example_strings)


if __name__ == '__main__':
    examples = [{
        "user": "今天北京天气如何",
        "assistant": """<tool_assistant>
                            {
                                "server": [工具平台类型，如'文件操作'、'数据分析'等]
                                "tool": [具体需要什么工具来做什么事]
                            }
                        </tool_assistant>""",
    }, {
        "user": """<tool_response>
                                {
                                    "server": 平台类型
                                    "tool"：工具名称
                                    "params"：参数列表，json格式，key是参数名，value是参数描述
                                }
                            </tool_response>""",
        "assistant": """<function_call>
                                {
                                    "invoke": 工具名称,
                                    "params": 参数列表，json格式，key是参数名，value是参数值
                                }
                            </function_call>""",
    }, {
        "user": """<function_call_response>
                                {
                                    "result":"xxx"
                                }
                            </function_call_response>""",
        "assistant": """<final_response>
                                {
                                    "content": "xxx"
                                }
                            <final_response>"""
    }, {
        "user": "你好",
        "assistant": """<final_response>
                            {
                                "content": "xxx"
                            }
                        <final_response>""",
    }, {
        "user": "今天是周几?",
        "assistant": """<tool_assistant>
                            {
                                "server": [工具平台类型，如'文件操作'、'数据分析'等]
                                "tool": [具体需要什么工具来做什么事]
                            }
                        </tool_assistant>"""
    }, {
        "user": "无法获取工具",
        "assistant": """<final_response>
                                {
                                    "content": "暂无法解决您的问题，非常抱歉"
                                }
                            <final_response>""",
    }]
    example_template = """
        User: {user}
        Assistant: {assistant}
    """
    example_prompt = examples_to_string(examples, example_template)
    prefix_prompt = """你是一位问题解决大师，根据用户的问题去解决问题，如果不需要工具可以完成任务，直接回复
                    <final_response>
                        {
                            "content": "xxx"
                        }
                    <final_response>
                    标签包裹答案，如果你发现现有能力无法完成任务时，请使用以下格式主动请求工具,你在收到结果以后，
                    若是结果满足回答问题了，直接进行回答问题，若是不满足，则继续按照上面步骤请求工具，直到可以回
                    答问题为止，注意你的回答需要带上下面示例的xml标签，严格按照上面的步骤进行,你在没有工具之前不
                    能返回<function_call>,在最终回复的时候回复<final_response>标签,以下是一些例子：\n"""
    prompt = prefix_prompt + example_prompt
    print(prompt)
    messages = [{'role': 'system', 'content': prompt}]
    llm = QwenLLM(api_key="sk-02bd21ded17c4dbba4c345fc4965534c", system_prompt=prompt)
    response = llm.llm_response("今天London天气如何？", messages)
    match = exists_tag(response, "final_response")
    if match:
        print(response)
    else:
        need_tool = extract_and_parse_tool_assistant(response, "tool_assistant")
        tool = '无法获取工具'
        if need_tool is not None:
            tool_desc = need_tool['tool']
            tool = get_tool(tool_desc)
        response = llm.llm_response(tool, messages)
        need_tool = extract_and_parse_tool_assistant(response, "function_call")
        for msg in messages:
            print(msg)
        clientTransport = StreamableHttpTransport("http://localhost:8001/mcp")
        result = asyncio.run(client_main(clientTransport, need_tool['invoke'], need_tool['params']))
        response = llm.llm_response(str(result), messages)
        print(response)

