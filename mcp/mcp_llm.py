import asyncio
import json
import os
import traceback
from typing import Optional
from contextlib import AsyncExitStack

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport, SSETransport
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.client = OpenAI(
            api_key="sk-02bd21ded17c4dbba4c345fc4965534c",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = "qwen-plus-character"
        self.messages = [
            {
                "role": "system",
                "content": "You are a versatile assistant capable of answering questions, completing tasks, and intelligently invoking specialized tools to deliver optimal results."
            }
        ]
        self.available_tools = []

    @staticmethod
    def convert_custom_object(obj):
        """
        将自定义对象转换为字典
        """
        if hasattr(obj, "__dict__"):  # 如果对象有 __dict__ 属性，直接使用
            return obj.__dict__
        elif isinstance(obj, (list, tuple)):  # 如果是列表或元组，递归处理
            return [MCPClient.convert_custom_object(item) for item in obj]
        elif isinstance(obj, dict):  # 如果是字典，递归处理值
            return {key: MCPClient.convert_custom_object(value) for key, value in obj.items()}
        else:  # 其他类型（如字符串、数字等）直接返回
            return obj

    async def connect_to_server(self):
        try:
            # clientTransport = StreamableHttpTransport("http://localhost:8001/mcp")
            clientTransport = SSETransport("http://localhost:8000/sse")
            self.session = await self.exit_stack.enter_async_context(Client(clientTransport))
            # 列出可用工具
            tools_response = await self.session.list_tools()
            print(f"Available tools:")
            for tool in tools_response:
                print(f" - {tool.name}: {tool.description}")
        except Exception as e:
            print(f'出错了：{e}')
            pass

    async def process_query(self, query: str) -> str:
        """Process a query with multi-turn tool calling support"""
        # Add user query to message history
        self.messages.append({
            "role": "user",
            "content": query
        })
        # Get available tools if not already set
        if not self.available_tools:
            tools_response = await self.session.list_tools()
            self.available_tools = [{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            } for tool in tools_response]
        current_response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.available_tools,
            stream=False
        )
        # Print initial response if exists
        if current_response.choices[0].message.content:
            print("\n  AI:", current_response.choices[0].message.content)
        # 直到下一次交互 AI 没有选择调用工具时退出循环
        while current_response.choices[0].message.tool_calls:
            # AI 一次交互中可能会调用多个工具
            for tool_call in current_response.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                print(f"\n  调用工具 {tool_name}")
                print(f"  参数: {tool_args}")
                # Execute tool call
                result = await self.session.call_tool(tool_name, tool_args)
                print(f"\n工具结果: {result}")
                # Add AI message and tool result to history
                self.messages.append(current_response.choices[0].message)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result[0].text)
                })
            # Get next response
            current_response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.available_tools,
                stream=False
            )
        # Add final response to history
        self.messages.append(current_response.choices[0].message)
        return current_response.choices[0].message.content or ""

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nCommend: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n AI: " + response)

            except Exception as e:
                print(f"\nError occurs: {e}")
                traceback.print_exc()

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()



async def main():
    client = MCPClient()
    try:
        await client.connect_to_server()
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())