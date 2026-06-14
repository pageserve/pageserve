import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:3000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== TOOLS ==")
            for t in tools.tools:
                print(f"- {t.name}: {(t.description or '').strip().splitlines()[0]}")

            # Ví dụ gọi thử list_documents
            print("\n== list_documents ==")
            res = await session.call_tool("list_documents", {})
            print(res.content[0].text)


asyncio.run(main())
