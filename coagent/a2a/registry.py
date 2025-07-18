try:
    from a2a.client import A2ACardResolver
except ImportError as exc:
    raise ImportError(
        "A2A package requires a2a-sdk. "
        "Install with 'pip install coagent-python[a2a]'"
    ) from exc

from coagent.core import AgentSpec, new
from coagent.core.types import Runtime
import httpx

from .agent import A2AAgent


class A2ARegistry:
    def __init__(self, runtime: Runtime, httpx_client: httpx.AsyncClient) -> None:
        self.runtime: Runtime = runtime
        self.httpx_client: httpx.AsyncClient = httpx_client

    async def register(self, url: str) -> str:
        resolver = A2ACardResolver(
            httpx_client=self.httpx_client,
            base_url=url,
        )
        card = await resolver.get_agent_card()

        name = normalize_agent_card_name(card.name)
        spec = AgentSpec(
            name,
            new(A2AAgent, httpx_client=self.httpx_client, card=card),
            card.description,
        )

        await self.runtime.register(spec)
        return name

    async def deregister(self, name: str) -> None:
        await self.runtime.deregister(name)


def normalize_agent_card_name(name: str) -> str:
    # Replace all spaces with underscores and convert to lowercase.
    return name.replace(" ", "_").lower()
