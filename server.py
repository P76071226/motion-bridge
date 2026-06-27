import asyncio
import json
import logging
import os
import socket
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PHONE_PORT = 8765
HTTP_PORT = 8080
DASHBOARD_DIR = Path(__file__).parent / "dashboard"

phone_ws = None
latest_data = None
browser_clients = set()

def get_lan_ip_candidates():
    candidates = []

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in candidates:
                candidates.append(ip)
    except socket.gaierror:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            ip = probe.getsockname()[0]
            if ip not in candidates:
                candidates.insert(0, ip)
    except OSError:
        pass

    if "127.0.0.1" not in candidates:
        candidates.append("127.0.0.1")

    return candidates

def build_status_payload(host=None, http_port=HTTP_PORT, websocket_port=PHONE_PORT, ip_candidates=None):
    candidates = ip_candidates or get_lan_ip_candidates()
    selected_host = host or candidates[0]

    return {
        "type": "status",
        "host": selected_host,
        "http_port": http_port,
        "websocket_port": websocket_port,
        "ip_candidates": candidates,
        "dashboard_url": f"http://{selected_host}:{http_port}",
        "phone_ws_url": f"ws://{selected_host}:{websocket_port}/phone",
        "phone_command": f"python phone_client.py --server {selected_host}",
    }

async def phone_handler(websocket, path):
    global phone_ws, latest_data
    phone_ws = websocket
    logger.info("Phone connected")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                latest_data = data
                await broadcast_to_browsers(data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from phone: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        phone_ws = None
        logger.info("Phone disconnected")
        await broadcast_to_browsers({"type": "disconnected"})

async def browser_handler(websocket, path):
    browser_clients.add(websocket)
    if latest_data:
        await websocket.send(json.dumps(latest_data))

    try:
        async for message in websocket:
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        browser_clients.discard(websocket)

async def broadcast_to_browsers(data):
    if browser_clients:
        message = json.dumps(data)
        await asyncio.gather(*[client.send(message) for client in browser_clients], return_exceptions=True)

async def router(websocket):
    path = websocket.request.path
    if path == "/phone":
        await phone_handler(websocket, path)
    else:
        await browser_handler(websocket, path)

async def ws_server():
    logger.info(f"WS server starting on port {PHONE_PORT}")
    async with websockets.serve(router, "0.0.0.0", PHONE_PORT, close_timeout=10):
        logger.info(f"Phone WS endpoint: ws://localhost:{PHONE_PORT}/phone")
        logger.info(f"Browser WS endpoint: ws://localhost:{PHONE_PORT}/")
        await asyncio.sleep(float('inf'))

def run_http_server():
    class DashboardHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/status":
                body = json.dumps(build_status_payload()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            super().do_GET()

        def translate_path(self, path):
            path = super().translate_path(path)
            rel = Path(path).relative_to(Path.cwd())
            return str(DASHBOARD_DIR / rel)

        def log_message(self, format, *args):
            logger.info(format % args)

    os.chdir(DASHBOARD_DIR)
    server = HTTPServer(("0.0.0.0", HTTP_PORT), DashboardHandler)
    logger.info(f"HTTP server serving {DASHBOARD_DIR} on port {HTTP_PORT}")
    logger.info(f"Dashboard: http://localhost:{HTTP_PORT}")
    server.serve_forever()

async def main():
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        loop.run_in_executor(executor, run_http_server)
        await ws_server()

if __name__ == "__main__":
    asyncio.run(main())
