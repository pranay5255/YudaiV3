import os
import json
from typing import List, Dict, Any
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from openai import OpenAI
from .utils.prompt import ClientMessage, convert_to_openai_messages
from .utils.tools import get_current_weather


load_dotenv(".env.local")

app = FastAPI()

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1",
)


class Request(BaseModel):
    messages: List[ClientMessage]


class DependencyAnalysisRequest(BaseModel):
    repoUrl: str


class DependencyItem(BaseModel):
    name: str
    type: str  # "internal" | "external"
    path: str = None
    version: str = None


class FileDependency(BaseModel):
    filename: str
    dependencies: List[DependencyItem]


class DependencyAnalysisResponse(BaseModel):
    dependencies: List[FileDependency]


class IdeasRequest(BaseModel):
    repoUrl: str
    context: str = None


class IdeaItem(BaseModel):
    id: int
    title: str
    description: str
    priority: str  # "high" | "medium" | "low"
    category: str  # "feature" | "enhancement" | "security"
    estimatedTime: str


class IdeasResponse(BaseModel):
    ideas: List[IdeaItem]


available_tools = {
    "get_current_weather": get_current_weather,
}

def do_stream(messages: List[ChatCompletionMessageParam]):
    stream = client.chat.completions.create(
        messages=messages,
        model="gpt-4o",
        stream=True,
        tools=[{
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather at a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "The latitude of the location",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "The longitude of the location",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        }]
    )

    return stream

def stream_text(messages: List[ChatCompletionMessageParam], protocol: str = 'data'):
    draft_tool_calls = []
    draft_tool_calls_index = -1

    stream = client.chat.completions.create(
        messages=messages,
        model="gpt-4o",
        stream=True,
        tools=[{
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather at a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "The latitude of the location",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "The longitude of the location",
                        },
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        }]
    )

    for chunk in stream:
        for choice in chunk.choices:
            if choice.finish_reason == "stop":
                continue

            elif choice.finish_reason == "tool_calls":
                for tool_call in draft_tool_calls:
                    yield '9:{{"toolCallId":"{id}","toolName":"{name}","args":{args}}}\n'.format(
                        id=tool_call["id"],
                        name=tool_call["name"],
                        args=tool_call["arguments"])

                for tool_call in draft_tool_calls:
                    tool_result = available_tools[tool_call["name"]](
                        **json.loads(tool_call["arguments"]))

                    yield 'a:{{"toolCallId":"{id}","toolName":"{name}","args":{args},"result":{result}}}\n'.format(
                        id=tool_call["id"],
                        name=tool_call["name"],
                        args=tool_call["arguments"],
                        result=json.dumps(tool_result))

            elif choice.delta.tool_calls:
                for tool_call in choice.delta.tool_calls:
                    id = tool_call.id
                    name = tool_call.function.name
                    arguments = tool_call.function.arguments

                    if (id is not None):
                        draft_tool_calls_index += 1
                        draft_tool_calls.append(
                            {"id": id, "name": name, "arguments": ""})

                    else:
                        draft_tool_calls[draft_tool_calls_index]["arguments"] += arguments

            else:
                yield '0:{text}\n'.format(text=json.dumps(choice.delta.content))

        if chunk.choices == []:
            usage = chunk.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens

            yield 'e:{{"finishReason":"{reason}","usage":{{"promptTokens":{prompt},"completionTokens":{completion}}},"isContinued":false}}\n'.format(
                reason="tool-calls" if len(
                    draft_tool_calls) > 0 else "stop",
                prompt=prompt_tokens,
                completion=completion_tokens
            )


@app.post("/api/chat")
async def handle_chat_data(request: Request, protocol: str = Query('data')):
    messages = request.messages
    openai_messages = convert_to_openai_messages(messages)

    response = StreamingResponse(stream_text(openai_messages, protocol))
    response.headers['x-vercel-ai-data-stream'] = 'v1'
    return response


@app.post("/api/analyze-dependencies")
async def analyze_dependencies(request: DependencyAnalysisRequest) -> DependencyAnalysisResponse:
    """
    Analyze dependencies for a given repository URL.
    In a real implementation, this would clone the repo and analyze the actual files.
    For now, we return mock data.
    """
    
    # Mock data for demonstration
    mock_dependencies = [
        FileDependency(
            filename="components/appSidebar.tsx",
            dependencies=[
                DependencyItem(name="react", type="external", version="^18.0.0"),
                DependencyItem(name="lucide-react", type="external", version="^0.263.1"),
                DependencyItem(name="@/components/ui/sidebar", type="internal", path="./ui/sidebar"),
                DependencyItem(name="@/lib/utils", type="internal", path="./lib/utils")
            ]
        ),
        FileDependency(
            filename="components/chat.tsx",
            dependencies=[
                DependencyItem(name="react", type="external", version="^18.0.0"),
                DependencyItem(name="@/components/ui/button", type="internal", path="./ui/button"),
                DependencyItem(name="@/components/ui/textarea", type="internal", path="./ui/textarea"),
                DependencyItem(name="ai", type="external", version="^3.0.0")
            ]
        ),
        FileDependency(
            filename="app/layout.tsx",
            dependencies=[
                DependencyItem(name="next", type="external", version="^14.0.0"),
                DependencyItem(name="geist/font/sans", type="external", version="^1.0.0"),
                DependencyItem(name="sonner", type="external", version="^1.0.0"),
                DependencyItem(name="@/lib/utils", type="internal", path="./lib/utils")
            ]
        ),
        FileDependency(
            filename="api/index.py",
            dependencies=[
                DependencyItem(name="fastapi", type="external", version="^0.111.1"),
                DependencyItem(name="openai", type="external", version="^1.37.1"),
                DependencyItem(name="pydantic", type="external", version="^2.8.2"),
                DependencyItem(name="python-dotenv", type="external", version="^1.0.1")
            ]
        )
    ]
    
    return DependencyAnalysisResponse(dependencies=mock_dependencies)


@app.post("/api/generate-ideas")
async def generate_ideas(request: IdeasRequest) -> IdeasResponse:
    """
    Generate improvement ideas for a given repository.
    In a real implementation, this would use AI to analyze the codebase and generate suggestions.
    For now, we return mock data.
    """
    
    # Mock data for demonstration
    mock_ideas = [
        IdeaItem(
            id=1,
            title="Implement Real-time Collaboration",
            description="Add WebSocket support for multiple users to collaborate on the same repository analysis in real-time.",
            priority="high",
            category="feature",
            estimatedTime="2 weeks"
        ),
        IdeaItem(
            id=2,
            title="Add Code Quality Metrics",
            description="Integrate code complexity analysis, test coverage reports, and technical debt assessment.",
            priority="medium",
            category="enhancement",
            estimatedTime="1 week"
        ),
        IdeaItem(
            id=3,
            title="Export Analysis Reports",
            description="Allow users to export dependency analysis and chat conversations as PDF or markdown reports.",
            priority="low",
            category="feature",
            estimatedTime="3 days"
        ),
        IdeaItem(
            id=4,
            title="Dependency Security Scanning",
            description="Scan external dependencies for known vulnerabilities and provide security recommendations.",
            priority="high",
            category="security",
            estimatedTime="1 week"
        )
    ]
    
    return IdeasResponse(ideas=mock_ideas)
