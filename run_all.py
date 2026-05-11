"""
Launch all 6 MCP intelligence servers on their respective ports.

Usage:
    python run_all.py          # Start all servers
    python run_all.py --only edgar-signals ai-labs   # Start specific servers

Ports:
    edgar-signals   8100
    ai-labs         8101
    earnings-intel  8102
    govcon          8103
    hiring-signals  8104
    infra-signals   8105
"""

import argparse
import asyncio
import logging
import signal
import sys
import os

# Ensure the parent directory is on the path so 'shared' can be imported
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("run_all")

SERVERS = {
    "edgar-signals": {"module": "edgar-signals.server", "port": 8100},
    "ai-labs": {"module": "ai-labs.server", "port": 8101},
    "earnings-intel": {"module": "earnings-intel.server", "port": 8102},
    "govcon": {"module": "govcon.server", "port": 8103},
    "hiring-signals": {"module": "hiring-signals.server", "port": 8104},
    "infra-signals": {"module": "infra-signals.server", "port": 8105},
}

# Map module paths to their FastAPI app import strings for uvicorn
APP_PATHS = {
    "edgar-signals": "edgar-signals.server:app",
    "ai-labs": "ai-labs.server:app",
    "earnings-intel": "earnings-intel.server:app",
    "govcon": "govcon.server:app",
    "hiring-signals": "hiring-signals.server:app",
    "infra-signals": "infra-signals.server:app",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Launch MCP intelligence servers")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=list(SERVERS.keys()),
        help="Only start these specific servers",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    return parser.parse_args()


async def run_server(name: str, port: int, host: str):
    """Run a single uvicorn server in an async task."""
    # Dynamic import of the app
    if name == "edgar-signals":
        from importlib import import_module
        mod = import_module("edgar-signals.server", package=None)
    elif name == "ai-labs":
        from importlib import import_module
        mod = import_module("ai-labs.server", package=None)
    elif name == "earnings-intel":
        from importlib import import_module
        mod = import_module("earnings-intel.server", package=None)
    elif name == "govcon":
        from importlib import import_module
        mod = import_module("govcon.server", package=None)
    elif name == "hiring-signals":
        from importlib import import_module
        mod = import_module("hiring-signals.server", package=None)
    elif name == "infra-signals":
        from importlib import import_module
        mod = import_module("infra-signals.server", package=None)
    else:
        logger.error(f"Unknown server: {name}")
        return

    app = mod.app
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"Starting {name} on {host}:{port}")
    await server.serve()


async def main():
    args = parse_args()
    selected = args.only if args.only else list(SERVERS.keys())

    logger.info(f"Starting {len(selected)} MCP servers: {', '.join(selected)}")

    tasks = []
    for name in selected:
        info = SERVERS[name]
        tasks.append(asyncio.create_task(run_server(name, info["port"], args.host)))

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown_handler():
        logger.info("Shutdown signal received, stopping all servers...")
        for task in tasks:
            task.cancel()

    try:
        loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        logger.info("All servers stopped")


if __name__ == "__main__":
    asyncio.run(main())
