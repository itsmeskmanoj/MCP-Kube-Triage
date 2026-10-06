import argparse
from typing import Literal, cast

from kube_triage.server import mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Kubernetes operations MCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
    )
    args = parser.parse_args()
    transport = cast(Literal["stdio", "streamable-http"], args.transport)

    if transport == "stdio":
        mcp.run()
        return

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()