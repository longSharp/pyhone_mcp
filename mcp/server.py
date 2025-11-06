# weather_sse.py
import sys

from fastmcp import FastMCP
import random

# 创建MCP服务器实例，指定端口
mcp = FastMCP("Weather Service")

# 模拟的天气数据
weather_data = {
    "New York": {"temp": range(10, 25), "conditions": ["sunny", "cloudy", "rainy"]},
    "London": {"temp": range(5, 20), "conditions": ["cloudy", "rainy", "foggy"]},
    "Tokyo": {"temp": range(15, 30), "conditions": ["sunny", "cloudy", "humid"]},
    "Sydney": {"temp": range(20, 35), "conditions": ["sunny", "clear", "hot"]},
    "北京": {"temp": range(20, 35), "conditions": ["晴天"]},
}


@mcp.tool(description="获取天气")
def get_weather(city: str) -> dict:
    if city not in weather_data:
        return {"error": f"无法找到城市 {city} 的天气数据"}

    data = weather_data[city]
    temp = random.choice(list(data["temp"]))
    condition = random.choice(data["conditions"])

    return {
        "city": city,
        "temperature": temp,
        "condition": condition,
        "unit": "celsius"
    }


@mcp.resource("weather://cities")
def get_available_cities() -> list:
    """获取所有可用的城市列表"""
    return list(weather_data.keys())


@mcp.resource("weather://forecast/{city}")
def get_forecast(city: str) -> dict:
    """获取指定城市的天气预报资源"""
    if city not in weather_data:
        return {"error": f"无法找到城市 {city} 的天气预报"}

    forecast = []
    for i in range(5):  # 5天预报
        data = weather_data[city]
        temp = random.choice(list(data["temp"]))
        condition = random.choice(data["conditions"])
        forecast.append({
            "day": i + 1,
            "temperature": temp,
            "condition": condition
        })

    return {
        "city": city,
        "forecast": forecast,
        "unit": "celsius"
    }


if __name__ == "__main__":
    transport = 'stream'
    if len(sys.argv) > 1:
        transport = sys.argv[1]
    # 启动服务器
    if transport == 'sse':
        mcp.run(transport=transport, port=8000, path="")
    elif transport == 'stdio':
        mcp.run(transport=transport)
    elif transport == 'stream':
        mcp.run(transport="streamable-http", host="127.0.0.1", port=8001, path="")