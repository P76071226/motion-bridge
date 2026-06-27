#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import queue
import signal
import subprocess
import sys
import threading
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PhoneClient:
    def __init__(self, server_url):
        self.server_url = server_url
        self.ws = None
        self.sensor_process = None
        self.sensor_thread = None
        self.sensor_queue = None
        self.loop = None
        self.reconnect_delay = 1
        self.max_reconnect_delay = 5
        self.running = True

    def start_sensor(self):
        try:
            if not self.sensor_queue:
                self.sensor_queue = queue.Queue()
            self.sensor_process = subprocess.Popen(
                ["termux-sensor", "-s", "Rotation Vector", "-d", "100"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            logger.info("Sensor process started (Rotation Vector)")
            self.sensor_thread = threading.Thread(target=self._read_sensor, daemon=True)
            self.sensor_thread.start()
        except FileNotFoundError:
            logger.error("termux-sensor not found. Install Termux:API first.")
            sys.exit(1)

    def _read_sensor(self):
        buffer = ""
        try:
            for line in iter(self.sensor_process.stdout.readline, ''):
                if not self.running:
                    break
                buffer += line
                try:
                    if buffer.strip().endswith("}"):
                        data = json.loads(buffer)
                        buffer = ""
                        if isinstance(data, dict) and data:
                            try:
                                self.sensor_queue.put(data, block=False)
                            except queue.Full:
                                pass
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Sensor read error: {e}")

    def stop_sensor(self):
        self.running = False
        if self.sensor_process:
            self.sensor_process.terminate()
            try:
                _, stderr = self.sensor_process.communicate(timeout=2)
                if stderr:
                    logger.error(f"Sensor stderr: {stderr}")
            except subprocess.TimeoutExpired:
                self.sensor_process.kill()
        if self.sensor_thread:
            self.sensor_thread.join(timeout=1)
        logger.info("Sensor process stopped")

    async def connect(self):
        while True:
            try:
                logger.info(f"Connecting to {self.server_url}")
                self.ws = await websockets.connect(self.server_url, close_timeout=10)
                self.reconnect_delay = 1
                logger.info("Connected to server")
                return
            except Exception as e:
                logger.error(f"Connection failed: {e}. Retrying in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 1.5, self.max_reconnect_delay)

    async def process_sensor_queue(self):
        first_data = True
        while self.running:
            try:
                data = self.sensor_queue.get(block=False)

                sensor_key = None
                for key in data.keys():
                    if "Rotation Vector" in key:
                        sensor_key = key
                        break

                if sensor_key and isinstance(data[sensor_key], dict):
                    values = data[sensor_key].get("values", [])
                    if len(values) >= 4:
                        if first_data:
                            logger.info(f"Sensor data received: {values[:4]}")
                            first_data = False

                        quat = {
                            "x": round(values[0], 4),
                            "y": round(values[1], 4),
                            "z": round(values[2], 4),
                            "w": round(values[3], 4)
                        }
                        message = {
                            "type": "orientation",
                            "quaternion": quat
                        }
                        if self.ws:
                            try:
                                await self.ws.send(json.dumps(message))
                            except Exception as e:
                                logger.error(f"Failed to send: {e}")
                                return
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error processing sensor data: {e}")

    async def run(self):
        self.start_sensor()
        while True:
            try:
                await self.connect()
                await self.process_sensor_queue()
            except websockets.exceptions.ConnectionClosed:
                logger.info("Connection closed by server")
            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            await asyncio.sleep(1)
        self.stop_sensor()

    def handle_signal(self, signum, frame):
        logger.info("Shutting down...")
        self.stop_sensor()
        if self.ws:
            asyncio.create_task(self.ws.close())
        sys.exit(0)

async def main():
    parser = argparse.ArgumentParser(description="Phone sensor client for orientation dashboard")
    parser.add_argument("--server", default="192.168.1.100", help="Server IP or full WebSocket URL")
    args = parser.parse_args()

    server_url = args.server
    if not server_url.startswith("ws://") and not server_url.startswith("wss://"):
        server_url = f"ws://{server_url}:8765/phone"

    client = PhoneClient(server_url)
    signal.signal(signal.SIGINT, client.handle_signal)
    signal.signal(signal.SIGTERM, client.handle_signal)

    await client.run()

if __name__ == "__main__":
    asyncio.run(main())
