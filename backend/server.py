import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from websockets.asyncio.server import ServerConnection, serve

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Connect4Server:
    """
    Connect Four Server that manages game state, players, and communication.
    """

    def __init__(self) -> None:
        """
        Initializes the Connect4Server with default game settings and state.
        """
        self.frontend_ws: Optional[ServerConnection] = None
        self.agent1_ws: Optional[ServerConnection] = None
        self.agent2_ws: Optional[ServerConnection] = None

        self.rows: int = 6
        self.cols: int = 7
        self.board: List[List[int]] = [
            [0 for _ in range(self.cols)] for _ in range(self.rows)
        ]

        self.first_player_this_round: int = 1
        self.current_turn: int = 1
        self.running: bool = False

        self.scores: Dict[int, int] = {1: 0, 2: 0}

    async def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """
        Starts the Connect Four WebSocket server.

        Args:
            host: The host address to bind the server to.
            port: The port number to listen on.
        """
        logging.info(f"Connect Four Server started on ws://{host}:{port}")
        async with serve(self.handle_client, host, port):
            await asyncio.Future()

    async def handle_client(
        self, websocket: ServerConnection
    ) -> None:
        """
        Handles incoming WebSocket connections and routes them based on client type.

        Args:
            websocket: The WebSocket connection object.
        """
        client_type: str = "Unknown"
        try:
            init_msg = await websocket.recv()
            if isinstance(init_msg, bytes):
                init_msg = init_msg.decode("utf-8")
            data: Dict[str, Any] = json.loads(init_msg)
            client_type = data.get("client", "Unknown")

            if client_type == "frontend":
                logging.info("Frontend connected.")
                self.frontend_ws = websocket
                await self.update_frontend()
                await self.frontend_loop(websocket)
            elif client_type == "agent":
                if not self.agent1_ws:
                    self.agent1_ws = websocket
                    logging.info("Player 1 connected.")
                    try:
                        await websocket.send(
                            json.dumps({"type": "setup", "player_id": 1})
                        )
                    except Exception:
                        self.agent1_ws = None
                        return
                    await self.check_start_conditions()
                    await self.agent_loop(websocket, 1)
                elif not self.agent2_ws:
                    self.agent2_ws = websocket
                    logging.info("Player 2 connected.")
                    try:
                        await websocket.send(
                            json.dumps({"type": "setup", "player_id": 2})
                        )
                    except Exception:
                        self.agent2_ws = None
                        return
                    await self.check_start_conditions()
                    await self.agent_loop(websocket, 2)
                else:
                    logging.warning("A 3rd agent tried to connect. Rejected.")
                    await websocket.close()
        except Exception as e:
            logging.error(f"Error handling client {client_type}: {e}")
        finally:
            if websocket == self.frontend_ws:
                self.frontend_ws = None
            elif websocket == self.agent1_ws:
                self.agent1_ws = None
                self.running = False
                logging.info("Player 1 disconnected. Pausing game.")
                await self.update_frontend()
            elif websocket == self.agent2_ws:
                self.agent2_ws = None
                self.running = False
                logging.info("Player 2 disconnected. Pausing game.")
                await self.update_frontend()

    async def frontend_loop(
        self, websocket: ServerConnection
    ) -> None:
        """
        Keeps the frontend connection alive.

        Args:
            websocket: The frontend WebSocket connection object.
        """
        async for _ in websocket:
            pass  # Frontend is view-only for now

    async def agent_loop(
        self, websocket: ServerConnection, player_id: int
    ) -> None:
        """
        Main loop for communicating with game agents.

        Args:
            websocket: The agent WebSocket connection object.
            player_id: The ID of the player (1 or 2).
        """
        async for message in websocket:
            if not self.running or self.current_turn != player_id:
                continue
            try:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                data: Dict[str, Any] = json.loads(message)
                if data.get("action") == "move" and isinstance(data.get("column"), int):
                    col: int = data["column"]
                    row: Optional[int] = self.process_move(player_id, col)
                    if row is not None:
                        await self.update_frontend()
                        if await self.check_game_over(row, col):
                            continue  # Round ended, don't swap turns here

                        self.current_turn = 3 - self.current_turn
                        await self.broadcast_state()
            except Exception as e:
                logging.error(f"Error processing move for Player {player_id}: {e}")

    async def check_start_conditions(self) -> None:
        """
        Checks if both agents are connected and starts the game if they are.
        """
        if self.agent1_ws and self.agent2_ws and not self.running:
            logging.info(f"Both agents connected. Starting round. Player {self.first_player_this_round} goes first.")
            self.running = True
            self.board = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
            self.current_turn = self.first_player_this_round
            await self.update_frontend()
            await self.broadcast_state()

    def get_valid_actions(self) -> List[int]:
        """
        Returns a list of column indices [0-6] that are not full.

        Returns:
            List of valid column indices.
        """
        return [c for c in range(self.cols) if self.board[0][c] == 0]

    def process_move(self, player_id: int, col: int) -> Optional[int]:
        """
        Processes a move for a player.

        Args:
            player_id: The ID of the player making the move.
            col: The column index where the piece is dropped.

        Returns:
            The row index where the piece landed, or None if the move was invalid.
        """
        if col not in self.get_valid_actions():
            logging.warning(f"Player {player_id} attempted invalid move in column {col}")
            return None

        # Gravity: drop the piece to the lowest available row
        for r in range(self.rows - 1, -1, -1):
            if self.board[r][col] == 0:
                self.board[r][col] = player_id
                return r
        return None

    async def check_game_over(self, last_row: int, last_col: int) -> bool:
        """
        Checks if the game has ended in a win or draw.

        Args:
            last_row: The row index of the last move.
            last_col: The column index of the last move.

        Returns:
            True if the game is over, False otherwise.
        """
        winner: int = self.check_win(last_row, last_col)
        valid_actions: List[int] = self.get_valid_actions()

        if winner:
            logging.info(f"Player {winner} wins the round!")
            self.scores[winner] += 1
            await self.end_round(f"Player {winner} Wins!")
            return True
        elif not valid_actions:
            logging.info("Round ended in a Draw.")
            await self.end_round("Draw!")
            return True
        return False

    def check_win(self, r: int, c: int) -> int:
        """
        Checks for 4 in a row intersecting the last move (r, c).

        Args:
            r: Row index of the last move.
            c: Column index of the last move.

        Returns:
            The ID of the winning player, or 0 if no win was found.
        """
        b = self.board
        p = b[r][c]
        if p == 0:
            return 0

        directions = [
            (0, 1),  # Horizontal
            (1, 0),  # Vertical
            (1, 1),  # Diagonal /
            (1, -1),  # Diagonal \
        ]

        for dr, dc in directions:
            count = 1
            # Check in positive direction
            for i in range(1, 4):
                nr, nc = r + dr * i, c + dc * i
                if 0 <= nr < self.rows and 0 <= nc < self.cols and b[nr][nc] == p:
                    count += 1
                else:
                    break
            # Check in negative direction
            for i in range(1, 4):
                nr, nc = r - dr * i, c - dc * i
                if 0 <= nr < self.rows and 0 <= nc < self.cols and b[nr][nc] == p:
                    count += 1
                else:
                    break
            if count >= 4:
                return p
        return 0

    async def end_round(self, message: str) -> None:
        """
        Notifies agents of the outcome, swaps the starting player, and restarts.

        Args:
            message: Game outcome message.
        """
        self.running = False
        payload: Dict[str, Any] = {
            "type": "game_over",
            "message": message,
            "scores": self.scores,
            "board": self.board,
        }
        await self.broadcast_to_agents(payload)
        await self.update_frontend(game_over_msg=message)

        # Pause briefly so humans can see the winning move on the UI
        await asyncio.sleep(2.0)

        # Swap who goes first and restart automatically
        self.first_player_this_round = 3 - self.first_player_this_round
        # Re-check connections after sleep
        if self.agent1_ws and self.agent2_ws:
            await self.check_start_conditions()
        else:
            logging.info("Round ended and an agent disconnected. Waiting for players...")

    async def broadcast_to_agents(self, payload: Dict[str, Any]) -> None:
        """
        Sends a message to both connected agents.

        Args:
            payload: The message to send.
        """
        msg: str = json.dumps(payload)
        # Handle agent1_ws
        if self.agent1_ws:
            try:
                await self.agent1_ws.send(msg)
            except Exception:
                self.agent1_ws = None
                logging.info("Player 1 disconnected during broadcast.")
        # Handle agent2_ws
        if self.agent2_ws:
            try:
                await self.agent2_ws.send(msg)
            except Exception:
                self.agent2_ws = None
                logging.info("Player 2 disconnected during broadcast.")

    async def broadcast_state(self) -> None:
        """
        Sends the board and valid actions to BOTH players.
        """
        payload: Dict[str, Any] = {
            "type": "state",
            "board": self.board,
            "valid_actions": self.get_valid_actions(),
            "current_turn": self.current_turn,
        }
        await self.broadcast_to_agents(payload)

    async def update_frontend(self, game_over_msg: Optional[str] = None) -> None:
        """
        Sends current game state to the frontend.

        Args:
            game_over_msg: Optional game over message to display on the frontend.
        """
        if self.frontend_ws:
            payload: Dict[str, Any] = {
                "type": "update",
                "board": self.board,
                "scores": self.scores,
                "current_turn": self.current_turn,
                "p1_connected": self.agent1_ws is not None,
                "p2_connected": self.agent2_ws is not None,
                "game_over": game_over_msg,
            }
            try:
                await self.frontend_ws.send(json.dumps(payload))
            except Exception:
                self.frontend_ws = None
                logging.info("Frontend disconnected.")


if __name__ == "__main__":
    server = Connect4Server()
    asyncio.run(server.start())
