import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import random
import time
import atexit
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent_train import BaseC4Agent

ROWS = 6
COLS = 7
DEPTH = 6

EXACT = "EXACT"
LOWERBOUND = "LOWERBOUND"
UPPERBOUND = "UPPERBOUND"


@dataclass
class TTEntry:
    """Entry stored in the transposition table."""
    depth: int
    value: float
    flag: str
    best_col: Optional[int]


class MinimaxC4Agent(BaseC4Agent):

    def __init__(self, server_uri: Optional[str] = None, depth: int = DEPTH) -> None:
        super().__init__(server_uri)
        self.depth = depth
        self.opponent_id: Optional[int] = None

        # Zobrist Hashing:
        # Each position (row, col, player) gets a random 64-bit number.
        # A board hash is the XOR of all occupied positions.
        rng = random.Random(42)  # fixed seed -> deterministic behaviour between runs
        self.zobrist_table = [
            [[rng.getrandbits(64) for _ in range(3)] for _ in range(COLS)]
            for _ in range(ROWS)
        ]

        # Transposition Table:
        # key -> TTEntry. The key includes the hash and whose turn it is.
        self.transposition_table: Dict[Tuple[int, bool], TTEntry] = {}
        self.max_tt_entries = 250_000

        # Métricas de desempenho por jogada.
        self.move_times: List[float] = []
        self.nodes_per_move: List[int] = []
        self.tt_hits_per_move: List[int] = []
        self._nodes_searched = 0
        self._tt_hits = 0
        self.metrics_output_path = "minimax_tt_zobrist_performance.png"
        self._performance_graph_saved = False

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

        board_copy = [row[:] for row in board]

        start_time = time.perf_counter()
        self._nodes_searched = 0
        self._tt_hits = 0

        col = await asyncio.to_thread(self.choose_move, board_copy, valid_actions)

        elapsed_time = time.perf_counter() - start_time
        self.move_times.append(elapsed_time)
        self.nodes_per_move.append(self._nodes_searched)
        self.tt_hits_per_move.append(self._tt_hits)

        logging.info(
            "Move %d | col=%s | time=%.4fs | nodes=%d | tt_hits=%d",
            len(self.move_times),
            col,
            elapsed_time,
            self._nodes_searched,
            self._tt_hits,
        )

        return col

    def choose_move(self, board: List[List[int]], valid_actions: List[int]) -> int:
        best_col = random.choice(valid_actions)
        best_score = float("-inf")
        alpha = float("-inf")
        beta = float("inf")

        board_hash = self._zobrist_hash(board)

        # Evita crescimento infinito caso o agente jogue durante muitas partidas.
        if len(self.transposition_table) > self.max_tt_entries:
            self.transposition_table.clear()

        for col in self._ordered_columns(valid_actions):
            dropped = self._drop_with_hash(board, col, self.player_id, board_hash)
            if dropped is None:
                continue

            b, child_hash = dropped
            score = self._minimax(
                b,
                self.depth - 1,
                alpha,
                beta,
                maximizing=False,
                board_hash=child_hash,
            )

            if score > best_score:
                best_score = score
                best_col = col

            # Também atualizamos alpha ao nível da raiz.
            alpha = max(alpha, best_score)

        return best_col

    def _minimax(
        self,
        board: List[List[int]],
        depth: int,
        alpha: float,
        beta: float,
        maximizing: bool,
        board_hash: int,
    ) -> float:
        self._nodes_searched += 1

        alpha_original = alpha
        beta_original = beta
        tt_key = (board_hash, maximizing)

        entry = self.transposition_table.get(tt_key)
        if entry is not None and entry.depth >= depth:
            self._tt_hits += 1
            if entry.flag == EXACT:
                return entry.value
            if entry.flag == LOWERBOUND:
                alpha = max(alpha, entry.value)
            elif entry.flag == UPPERBOUND:
                beta = min(beta, entry.value)

            if alpha >= beta:
                return entry.value

        if self._check_win(board, self.player_id):
            return 1_000_000 + depth
        if self._check_win(board, self.opponent_id):
            return -(1_000_000 + depth)

        valid = [c for c in range(COLS) if board[0][c] == 0]
        if not valid or depth == 0:
            return self.evaluate_board(board)

        best_col: Optional[int] = entry.best_col if entry is not None else None

        if maximizing:
            value = float("-inf")
            for col in self._ordered_columns(valid, first_col=best_col):
                dropped = self._drop_with_hash(board, col, self.player_id, board_hash)
                if dropped is None:
                    continue

                b, child_hash = dropped
                child_value = self._minimax(
                    b,
                    depth - 1,
                    alpha,
                    beta,
                    maximizing=False,
                    board_hash=child_hash,
                )

                if child_value > value:
                    value = child_value
                    best_col = col

                alpha = max(alpha, value)
                if alpha >= beta:
                    break
        else:
            value = float("inf")
            for col in self._ordered_columns(valid, first_col=best_col):
                dropped = self._drop_with_hash(board, col, self.opponent_id, board_hash)
                if dropped is None:
                    continue

                b, child_hash = dropped
                child_value = self._minimax(
                    b,
                    depth - 1,
                    alpha,
                    beta,
                    maximizing=True,
                    board_hash=child_hash,
                )

                if child_value < value:
                    value = child_value
                    best_col = col

                beta = min(beta, value)
                if alpha >= beta:
                    break

        if value <= alpha_original:
            flag = UPPERBOUND
        elif value >= beta_original:
            flag = LOWERBOUND
        else:
            flag = EXACT

        self.transposition_table[tt_key] = TTEntry(
            depth=depth,
            value=value,
            flag=flag,
            best_col=best_col,
        )

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

    def _zobrist_hash(self, board: List[List[int]]) -> int:
        """Computes the Zobrist hash of the current board."""
        h = 0
        for r in range(ROWS):
            for c in range(COLS):
                player = board[r][c]
                if player != 0:
                    h ^= self.zobrist_table[r][c][player]
        return h

    def _drop_with_hash(
        self,
        board: List[List[int]],
        col: int,
        player: int,
        board_hash: int,
    ) -> Optional[Tuple[List[List[int]], int]]:
        """
        Drops a piece and updates the Zobrist hash incrementally.

        Instead of recomputing the whole hash, we XOR only the random number
        corresponding to the newly occupied cell.
        """
        new_board = [row[:] for row in board]
        for r in range(ROWS - 1, -1, -1):
            if new_board[r][col] == 0:
                new_board[r][col] = player
                new_hash = board_hash ^ self.zobrist_table[r][col][player]
                return new_board, new_hash
        return None

    def _drop(self, board: List[List[int]], col: int, player: int) -> List[List[int]]:
        """Compatibility helper: drops a piece without returning the hash."""
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


    def save_performance_graph(self, output_path: Optional[str] = None) -> None:
        """Saves a graph with decision time and searched nodes per move."""
        if self._performance_graph_saved:
            return

        if not self.move_times:
            logging.info("No move metrics collected; performance graph was not generated.")
            return

        if plt is None:
            logging.warning("matplotlib is not installed; performance graph was not generated.")
            return

        output_path = output_path or self.metrics_output_path
        moves = list(range(1, len(self.move_times) + 1))

        fig, ax_time = plt.subplots(figsize=(10, 6))

        line_time = ax_time.plot(
            moves,
            self.move_times,
            marker="o",
            label="Tempo por jogada (s)",
        )
        ax_time.set_xlabel("Jogada")
        ax_time.set_ylabel("Tempo (segundos)")
        ax_time.grid(True, alpha=0.3)

        ax_nodes = ax_time.twinx()
        line_nodes = ax_nodes.plot(
            moves,
            self.nodes_per_move,
            marker="s",
            linestyle="--",
            label="Nós pesquisados",
        )
        ax_nodes.set_ylabel("Nós pesquisados")

        lines = line_time + line_nodes
        labels = [line.get_label() for line in lines]
        ax_time.legend(lines, labels, loc="upper left")

        plt.title("Desempenho do agente Minimax por jogada")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

        self._performance_graph_saved = True
        logging.info("Performance graph saved to %s", output_path)

    @staticmethod
    def _ordered_columns(valid: List[int], first_col: Optional[int] = None) -> List[int]:
        """Explores centre columns first and, if known, the TT best move before the others."""
        preferred = [3, 2, 4, 1, 5, 0, 6]
        ordered = [c for c in preferred if c in valid]

        if first_col is not None and first_col in ordered:
            ordered.remove(first_col)
            ordered.insert(0, first_col)

        return ordered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

    agent = MinimaxC4Agent()

    atexit.register(agent.save_performance_graph)

    logging.info("Starting Minimax Connect 4 Agent (depth=%d)...", agent.depth)
    try:
        asyncio.run(agent.run())
    finally:
        agent.save_performance_graph()
