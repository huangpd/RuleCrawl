"""
Integration test: verify that the DetailNode skips records
when a required field is empty.

The test spins up a tiny HTTP server that serves:
  - /list.html          – a list page with 4 links to detail pages
  - /detail_1.html      – has title AND price  (required field present)
  - /detail_2.html      – has title but NO price (required field missing)
  - /detail_3.html      – has title AND price  (required field present)
  - /detail_4.html      – has title but NO price (required field missing)

Expected result: only 2 records are saved (detail_1 and detail_3).
"""

import asyncio
import http.server
import json
import threading
import time
import uuid

import httpx

# ---------------------------------------------------------------------------
# 1. Mock HTTP server
# ---------------------------------------------------------------------------

PAGES = {
    "/list.html": (
        "<html><body>"
        '<div class="item"><a href="/detail_1.html">Item 1</a></div>'
        '<div class="item"><a href="/detail_2.html">Item 2</a></div>'
        '<div class="item"><a href="/detail_3.html">Item 3</a></div>'
        '<div class="item"><a href="/detail_4.html">Item 4</a></div>'
        "</body></html>"
    ),
    "/detail_1.html": (
        "<html><body>"
        '<h1 class="title">Product A</h1>'
        '<span class="price">$10.00</span>'
        "</body></html>"
    ),
    "/detail_2.html": (
        "<html><body>"
        '<h1 class="title">Product B</h1>'
        '<span class="price"></span>'  # empty required field
        "</body></html>"
    ),
    "/detail_3.html": (
        "<html><body>"
        '<h1 class="title">Product C</h1>'
        '<span class="price">$30.00</span>'
        "</body></html>"
    ),
    "/detail_4.html": (
        "<html><body>"
        '<h1 class="title">Product D</h1>'
        # no price element at all -> required field missing
        "</body></html>"
    ),
}

MOCK_PORT = 18932


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        pass  # suppress logs


def _start_mock_server():
    srv = http.server.HTTPServer(("127.0.0.1", MOCK_PORT), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


# ---------------------------------------------------------------------------
# 2. RuleCrawl API helpers
# ---------------------------------------------------------------------------

API = "http://127.0.0.1:8000/api/v1"


async def create_project(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{API}/projects", json={"name": "required-field-test"})
    r.raise_for_status()
    return r.json()["_id"]


async def create_node(client: httpx.AsyncClient, project_id: str, payload: dict) -> str:
    r = await client.post(f"{API}/projects/{project_id}/nodes", json=payload)
    r.raise_for_status()
    return r.json()["_id"]


async def set_callback(client: httpx.AsyncClient, node_id: str, target_id: str):
    r = await client.post(f"{API}/nodes/{node_id}/set-callback", params={"target_node_id": target_id})
    r.raise_for_status()


async def run_project(client: httpx.AsyncClient, project_id: str) -> str:
    r = await client.post(f"{API}/projects/{project_id}/run")
    r.raise_for_status()
    return r.json()["task_id"]


async def wait_task(client: httpx.AsyncClient, task_id: str, timeout: int = 60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = await client.get(f"{API}/tasks/{task_id}/status")
        r.raise_for_status()
        status = r.json().get("status")
        if status in ("completed", "failed", "stopped"):
            return r.json()
        await asyncio.sleep(2)
    raise TimeoutError(f"Task {task_id} did not finish within {timeout}s")


async def get_data(client: httpx.AsyncClient, project_id: str) -> list:
    r = await client.get(f"{API}/projects/{project_id}/data", params={"page_size": 100})
    r.raise_for_status()
    return r.json()["items"]


# ---------------------------------------------------------------------------
# 3. Main test
# ---------------------------------------------------------------------------

async def main():
    mock = _start_mock_server()
    print(f"Mock server running on http://127.0.0.1:{MOCK_PORT}")

    async with httpx.AsyncClient(timeout=30) as client:
        # --- health check RuleCrawl ---
        for _ in range(10):
            try:
                r = await client.get(f"{API}/projects")
                if r.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.ConnectTimeout):
                pass
            await asyncio.sleep(1)
        else:
            raise RuntimeError("RuleCrawl is not reachable at :8000")

        # --- create project ---
        project_id = await create_project(client)
        print(f"Project created: {project_id}")

        # --- create start node ---
        start_id = await create_node(client, project_id, {
            "node_type": "start",
            "name": "Seed",
            "request_config": {
                "url": [f"http://127.0.0.1:{MOCK_PORT}/list.html"],
            },
        })
        print(f"Start node: {start_id}")

        # --- create list node ---
        list_id = await create_node(client, project_id, {
            "node_type": "list",
            "name": "List Page",
            "parse_rules": {
                "parser_type": "css",
                "item_selector": "div.item",
                "item_selector_type": "css",
                "link_selector": "a::attr(href)",
                "link_selector_type": "css",
            },
        })
        print(f"List node: {list_id}")

        # --- create detail node with required "price" field ---
        detail_id = await create_node(client, project_id, {
            "node_type": "detail",
            "name": "Detail Page",
            "parse_rules": {
                "fields": [
                    {
                        "name": "title",
                        "selector": "h1.title::text",
                        "selector_type": "css",
                        "required": False,
                    },
                    {
                        "name": "price",
                        "selector": "span.price::text",
                        "selector_type": "css",
                        "required": True,   # <-- THIS IS THE KEY
                    },
                ],
            },
        })
        print(f"Detail node: {detail_id}")

        # --- wire callbacks: start -> list -> detail ---
        await set_callback(client, start_id, list_id)
        await set_callback(client, list_id, detail_id)
        print("Callbacks wired")

        # --- run ---
        task_id = await run_project(client, project_id)
        print(f"Task started: {task_id}")

        task = await wait_task(client, task_id)
        print(f"Task finished with status: {task['status']}")

        # --- verify ---
        data = await get_data(client, project_id)
        print(f"\nSaved records: {len(data)}")
        for rec in data:
            print(f"  - {rec['data']}")

        # We expect exactly 2 records (detail_1 with price=$10, detail_3 with price=$30)
        assert len(data) == 2, (
            f"Expected 2 saved records (those with non-empty price), got {len(data)}"
        )

        saved_prices = sorted(rec["data"].get("price", "") for rec in data)
        assert saved_prices == ["$10.00", "$30.00"], (
            f"Expected prices ['$10.00', '$30.00'], got {saved_prices}"
        )

        print("\n=== PASS: scraper correctly skipped records with empty required field ===")

    mock.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
