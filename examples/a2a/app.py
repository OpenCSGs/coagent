import httpx

from coagent.core import init_logger
from coagent.runtimes import LocalRuntime, NATSRuntime  # noqa: F401
from coagent.a2a.app import FastA2A

PORT = 8000

# runtime = LocalRuntime()
runtime = NATSRuntime.from_servers()
httpx_client = httpx.AsyncClient()
app = FastA2A(
    runtime=runtime,
    base_url=f"http://localhost:{PORT}",
    httpx_client=httpx_client,
    debug=True,
)


if __name__ == "__main__":
    init_logger("INFO")

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
