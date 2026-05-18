import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import random
import time
import atexit
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent_train import BaseC4Agent

ROWS = 6
COLS = 7
DEPTH = 6


class MinimaxC4Agent(BaseC4Agent):

    def __init__(self, server_uri: Optional[str] = None, depth: int = DEPTH) -> None:
        super().__init__(server_uri)
        self.depth = depth
        self.opponent_id: Optional[int] = None

        # Métricas por jogada
        self.move_times: List[float] = []
        self.move_nodes: List[int] = []
        self.current_nodes: int = 0

        # Tenta gerar o gráfico quando o programa terminar normalmente
        atexit.register(self.save_performance_graph)

    async def deliberate(self, valid_actions: List[int], data: Dict[str, Any]) -> Optional[int]:
        """
        Args:
            valid_actions: A list of valid column indices where a piece can be dropped.

        Returns:
            The chosen column index.
        """

        if not valid_actions:
            return None

        board = data.get("board")

        if board is None or self.player_id is None:
            return random.choice(valid_actions)

        self.opponent_id = 2 if self.player_id == 1 else 1

        # Cópia para evitar mutações acidentais durante a busca
        board_copy = [row[:] for row in board]

        self.current_nodes = 0
        start_time = time.perf_counter()

        col = await asyncio.to_thread(self.choose_move, board_copy, valid_actions)

        elapsed_time = time.perf_counter() - start_time
        self.move_times.append(elapsed_time)
        self.move_nodes.append(self.current_nodes)

        logging.info(
            "Jogada %d | coluna=%s | tempo=%.4fs | nós pesquisados=%d",
            len(self.move_times),
            col,
            elapsed_time,
            self.current_nodes,
        )

        return col

    def choose_move(self, board: List[List[int]], valid_actions: List[int]) -> int:
        best_col = random.choice(valid_actions)
        best_score = float("-inf")

        for col in self._ordered_columns(valid_actions):
            b = self._drop(board, col, self.player_id)
            score = self._minimax(b, self.depth - 1, float("-inf"), float("inf"), False)
            if score > best_score:
                best_score = score
                best_col = col

        return best_col

    def _minimax(self, board: List[List[int]], depth: int, alpha: float, beta: float, maximizing: bool) -> float:
        # Conta cada chamada ao minimax como um nó pesquisado
        self.current_nodes += 1

        if self._check_win(board, self.player_id):
            return 1_000_000 + depth
        if self._check_win(board, self.opponent_id):
            return -(1_000_000 + depth)

        valid = [c for c in range(COLS) if board[0][c] == 0]
        if not valid or depth == 0:
            return self.evaluate_board(board)

        if maximizing:
            value = float("-inf")
            for col in self._ordered_columns(valid):
                b = self._drop(board, col, self.player_id)
                value = max(value, self._minimax(b, depth - 1, alpha, beta, False))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = float("inf")
        for col in self._ordered_columns(valid):
            b = self._drop(board, col, self.opponent_id)
            value = min(value, self._minimax(b, depth - 1, alpha, beta, True))
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def evaluate_board(self, board: List[List[int]]) -> int:
        score = 0

        # Prefer centre column
        centre = [board[r][COLS // 2] for r in range(ROWS)]
        score += centre.count(self.player_id) * 4

        # Horizontal windows
        for r in range(ROWS):
            for c in range(COLS - 3):
                window = [board[r][c + i] for i in range(4)]
                score += self._score_window(window)

        # Vertical windows
        for c in range(COLS):
            for r in range(ROWS - 3):
                window = [board[r + i][c] for i in range(4)]
                score += self._score_window(window)

        # Diagonal ↘
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                window = [board[r + i][c + i] for i in range(4)]
                score += self._score_window(window)

        # Diagonal ↗
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                window = [board[r - i][c + i] for i in range(4)]
                score += self._score_window(window)

        return score

    def _score_window(self, window: List[int]) -> int:
        me = window.count(self.player_id)
        opp = window.count(self.opponent_id)
        empty = window.count(0)

        if me == 4:
            return 100
        if me == 3 and empty == 1:
            return 5
        if me == 2 and empty == 2:
            return 2
        if opp == 4:
            return -150
        if opp == 3 and empty == 1:
            return -4
        return 0

    def _drop(self, board: List[List[int]], col: int, player: int) -> List[List[int]]:
        new_board = [row[:] for row in board]
        for r in range(ROWS - 1, -1, -1):
            if new_board[r][col] == 0:
                new_board[r][col] = player
                break
        return new_board

    def _check_win(self, board: List[List[int]], player: int) -> bool:
        """Returns True if `player` has four in a row."""
        # Horizontal
        for r in range(ROWS):
            for c in range(COLS - 3):
                if all(board[r][c + i] == player for i in range(4)):
                    return True
        # Vertical
        for c in range(COLS):
            for r in range(ROWS - 3):
                if all(board[r + i][c] == player for i in range(4)):
                    return True
        # Diagonal ↘
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                if all(board[r + i][c + i] == player for i in range(4)):
                    return True
        # Diagonal ↗
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                if all(board[r - i][c + i] == player for i in range(4)):
                    return True
        return False

    @staticmethod
    def _ordered_columns(valid: List[int]) -> List[int]:
        """Explores centre columns first — improves Alpha-Beta pruning efficiency."""
        preferred = [3, 2, 4, 1, 5, 0, 6]
        return [c for c in preferred if c in valid]

    def save_performance_graph(self, filename: str = "minimax_original_performance.png") -> None:
        """Gera um gráfico com o tempo e os nós pesquisados por jogada."""
        if not self.move_times or not self.move_nodes:
            return

        if plt is None:
            logging.warning(
                "matplotlib não está instalado. Não foi possível gerar o gráfico de desempenho. "
                "Instala com: pip install matplotlib"
            )
            return

        moves = list(range(1, len(self.move_times) + 1))

        fig, ax1 = plt.subplots(figsize=(10, 6))

        ax1.set_xlabel("Jogada")
        ax1.set_ylabel("Tempo por jogada (s)")
        ax1.plot(moves, self.move_times, marker="o", label="Tempo por jogada (s)")
        ax1.tick_params(axis="y")

        ax2 = ax1.twinx()
        ax2.set_ylabel("Nós pesquisados")
        ax2.plot(moves, self.move_nodes, marker="x", linestyle="--", label="Nós pesquisados")
        ax2.tick_params(axis="y")

        plt.title("Desempenho do Minimax Original por Jogada")
        fig.tight_layout()
        plt.savefig(filename, dpi=300)
        plt.close(fig)

        logging.info("Gráfico de desempenho guardado em: %s", filename)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = MinimaxC4Agent()
    logging.info("Starting Original Minimax Connect 4 Agent with metrics (depth=%d)...", agent.depth)

    try:
        asyncio.run(agent.run())
    finally:
        # Garante que o gráfico é tentado no fim, mesmo em caso de interrupção/erro.
        agent.save_performance_graph()
