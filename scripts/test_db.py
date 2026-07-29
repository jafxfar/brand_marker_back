import asyncio
import asyncpg


async def main() -> None:
    for host, port in (("127.0.0.1", 5433), ("localhost", 5432)):
        try:
            conn = await asyncpg.connect(
                host=host,
                port=port,
                user="brandmarket",
                password="brandmarket",
                database="brandmarket",
                timeout=5,
            )
            val = await conn.fetchval("SELECT 1")
            print(f"{host}:{port}: OK -> {val}")
            await conn.close()
        except Exception as exc:
            print(f"{host}:{port}: FAIL -> {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
