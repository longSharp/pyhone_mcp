# sse_client.py
import asyncio
import sys

from fastmcp import Client
from fastmcp.client import SSETransport, StreamableHttpTransport, StdioTransport, ClientTransport


async def client_main(mcpClientTransport: ClientTransport):
    try:
        async with Client(mcpClientTransport) as client:
            # 列出可用工具
            tools_response = await client.list_tools()
            print(f"Available tools:")
            for tool in tools_response:
                print(f" - {tool.name}: {tool.description}")

            # 列出可用资源
            resources_response = await client.list_resources()
            print("\nAvailable resources:")
            for resource in resources_response:
                print(f" - {resource.uri}: {resource.description}")

            # 调用天气工具
            print("\nCalling get_weather tool for London...")
            weather_response = await client.call_tool("get_weather", {"city": "London"})
            print(weather_response)
            print(weather_response[0].text)

            # 读取资源
            print("\nReading weather://cities resource...")
            cities_response = await client.read_resource("weather://cities")
            print(cities_response[0].text)

            # 读取带参数的资源
            print("\nReading weather forecast for Tokyo...")
            forecast_response = await client.read_resource("weather://forecast/Tokyo")
            print(forecast_response[0].text)
    except Exception as e:
        print(f'出错了：{e}')
        pass


if __name__ == "__main__":
    clientTransport = None
    transport = 'sse'
    if len(sys.argv) > 1:
        transport = sys.argv[1]
    # 启动服务器
    if transport == 'sse':
        clientTransport = SSETransport("http://localhost:8000/mcp")
    elif transport == 'stdio':
        clientTransport = StdioTransport(command='python', args=['server.py'], cwd='D:\\code\\mcp\\python')
    elif transport == 'stream':
        clientTransport = StreamableHttpTransport("http://localhost:8001/mcp")
    asyncio.run(client_main(clientTransport))