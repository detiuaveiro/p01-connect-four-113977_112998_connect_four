import asyncio
import random
import math
from typing import List, Optional
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent_train import BaseC4Agent


ROWS = 6
COLS = 7
CENTER_COL = 3


class AlphaBetaAgent(BaseC4Agent):
    def __init__(self):
        super().__init__()
        self.DEPTH = 5

    async def deliberate(self, valid_actions: List[int], data) -> Optional[int]:
        await asyncio.sleep(0.2)

        board = data["board"]
        player = self.player_id
        opponent = 2 if player == 1 else 1

        best_col = self.choose_move(board, valid_actions, player, opponent)
        return best_col

    def choose_move(self, board, valid_actions, player, opponent):
        best_score = -math.inf
        best_col = random.choice(valid_actions)

        # ordenar jogadas: centro primeiro
        ordered_moves = self.order_moves(valid_actions)

        for col in ordered_moves:
            temp_board = self.copy_board(board)
            self.drop_piece(temp_board, col, player)

            score = self.minimax(
                temp_board,
                self.DEPTH - 1,
                -math.inf,
                math.inf,
                False,
                player,
                opponent
            )

            if score > best_score:
                best_score = score
                best_col = col

        return best_col

    def minimax(self, board, depth, alpha, beta, maximizing, player, opponent):
        valid_moves = self.get_valid_moves(board)

        if self.check_win(board, player):
            return 1000000 + depth

        if self.check_win(board, opponent):
            return -1000000 - depth

        if depth == 0 or not valid_moves:
            return self.evaluate_board(board, player, opponent)

        ordered_moves = self.order_moves(valid_moves)

        if maximizing:
            value = -math.inf

            for col in ordered_moves:
                temp_board = self.copy_board(board)
                self.drop_piece(temp_board, col, player)

                value = max(
                    value,
                    self.minimax(
                        temp_board,
                        depth - 1,
                        alpha,
                        beta,
                        False,
                        player,
                        opponent
                    )
                )

                alpha = max(alpha, value)

                if alpha >= beta:
                    break

            return value

        else:
            value = math.inf

            for col in ordered_moves:
                temp_board = self.copy_board(board)
                self.drop_piece(temp_board, col, opponent)

                value = min(
                    value,
                    self.minimax(
                        temp_board,
                        depth - 1,
                        alpha,
                        beta,
                        True,
                        player,
                        opponent
                    )
                )

                beta = min(beta, value)

                if alpha >= beta:
                    break

            return value

    def evaluate_board(self, board, player, opponent):
        score = 0

        # valorizar coluna central
        center_count = 0
        for row in range(ROWS):
            if board[row][CENTER_COL] == player:
                center_count += 1

        score += center_count * 6

        # avaliar todas as janelas de 4
        windows = self.get_all_windows(board)

        for window in windows:
            score += self.evaluate_window(window, player, opponent)

        return score

    def evaluate_window(self, window, player, opponent):
        score = 0

        player_count = window.count(player)
        opponent_count = window.count(opponent)
        empty_count = window.count(0)

        # ofensivo
        if player_count == 4:
            score += 100000
        elif player_count == 3 and empty_count == 1:
            score += 100
        elif player_count == 2 and empty_count == 2:
            score += 10

        # defensivo
        if opponent_count == 4:
            score -= 100000
        elif opponent_count == 3 and empty_count == 1:
            score -= 150
        elif opponent_count == 2 and empty_count == 2:
            score -= 15

        return score

    def get_all_windows(self, board):
        windows = []

        # horizontais
        for row in range(ROWS):
            for col in range(COLS - 3):
                windows.append([
                    board[row][col],
                    board[row][col + 1],
                    board[row][col + 2],
                    board[row][col + 3]
                ])

        # verticais
        for row in range(ROWS - 3):
            for col in range(COLS):
                windows.append([
                    board[row][col],
                    board[row + 1][col],
                    board[row + 2][col],
                    board[row + 3][col]
                ])

        # diagonais descendentes
        for row in range(ROWS - 3):
            for col in range(COLS - 3):
                windows.append([
                    board[row][col],
                    board[row + 1][col + 1],
                    board[row + 2][col + 2],
                    board[row + 3][col + 3]
                ])

        # diagonais ascendentes
        for row in range(3, ROWS):
            for col in range(COLS - 3):
                windows.append([
                    board[row][col],
                    board[row - 1][col + 1],
                    board[row - 2][col + 2],
                    board[row - 3][col + 3]
                ])

        return windows

    def check_win(self, board, player):
        for window in self.get_all_windows(board):
            if window.count(player) == 4:
                return True
        return False

    def get_valid_moves(self, board):
        return [col for col in range(COLS) if board[0][col] == 0]

    def drop_piece(self, board, col, player):
        for row in range(ROWS - 1, -1, -1):
            if board[row][col] == 0:
                board[row][col] = player
                return

    def copy_board(self, board):
        return [row[:] for row in board]

    def order_moves(self, valid_moves):
        preferred_order = [3, 2, 4, 1, 5, 0, 6]
        return [col for col in preferred_order if col in valid_moves]


if __name__ == "__main__":
    agent = AlphaBetaAgent()
    asyncio.run(agent.run())