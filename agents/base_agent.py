import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from websockets.asyncio.client import connect

# Add the parent directory to sys.path to allow running agents as scripts from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - AGENT - %(message)s")


class BaseC4Agent:
    """
    Abstract base class for Connect Four agents.
    Subclasses MUST implement the deliberate(valid_actions) method.
    """

    def __init__(self, server_uri: Optional[str] = None) -> None:
        """
        Initializes the agent with the server URI.

        Args:
            server_uri: The WebSocket URI of the Connect Four server.
        """
        self.server_uri: str = server_uri or os.environ.get("SERVER_URI", "ws://localhost:8765")
        self.player_id: Optional[int] = None

    async def run(self) -> None:
        """
        Connects to the server and enters the main communication loop.
        """
        try:
            async with connect(self.server_uri) as websocket:
                await websocket.send(json.dumps({"client": "agent"}))

                async for message in websocket:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    data: Dict[str, Any] = json.loads(message)

                    if data.get("type") == "setup":
                        self.player_id = data.get("player_id")
                        logging.info(f"Connected! Assigned Player {self.player_id}")

                    elif data.get("type") == "state":
                        current_turn = data.get("current_turn")
                        valid_actions = data.get("valid_actions")

                        if current_turn == self.player_id and isinstance(valid_actions, list):
                            # It's our turn! Ask the subclass to make a decision
                            action: Optional[int] = await self.deliberate(valid_actions)

                            if action is not None:
                                await websocket.send(json.dumps({"action": "move", "column": action}))

                    elif data.get("type") == "game_over":
                        logging.info(f"Round Over: {data.get('message')}")
                        logging.info("Waiting for next round to start...")

        except Exception as e:
            logging.error(f"Connection lost: {e}")

    async def deliberate(self, valid_actions: List[int]) -> Optional[int]:
        """
        MUST be implemented by subclasses.
        Returns an integer representing the chosen column [0-6].

        Args:
            valid_actions: A list of valid column indices where a piece can be dropped.

        Returns:
            The chosen column index, or None if no move is made.
        """
        raise NotImplementedError("Subclasses must implement deliberate()")
