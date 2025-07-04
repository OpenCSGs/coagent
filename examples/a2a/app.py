from coagent.core import set_stderr_logger
from coagent.runtimes import LocalRuntime, NATSRuntime
from coagent.a2a.app import FastA2A

PORT = 8000

# runtime = LocalRuntime()
runtime = NATSRuntime.from_servers()
app = FastA2A(runtime=runtime, base_url=f"http://localhost:{PORT}", debug=True)


if __name__ == "__main__":
    set_stderr_logger("INFO")

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
