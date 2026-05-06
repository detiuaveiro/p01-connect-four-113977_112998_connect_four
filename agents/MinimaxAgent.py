import asyncio
import os
import random
import sys
from typing import List, Optional

# Add the parent directory to sys.path to allow running agents as scripts from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent_train import BaseC4Agent


class MinimaxAgent(BaseC4Agent):
    """
    Agent that trains with another to learn best minimax tree
    """
    def __init__(self) -> None:
        super().__init__()
        self.valid_actions: List[int] = []
        self.board_weights = [[3,4,5,7,5,4,3],[4,6,8,10,8,6,4],[5,7,11,13,11,7,5],[5,7,11,13,11,7,5],[4,6,8,10,8,6,4],[3,4,5,7,5,4,3]]
        self.other_player_id: Optional[int] = None
        self.DEPTH_SEARCH = 4

    async def deliberate(self, valid_actions: List[int], data) -> Optional[int]:
        """
        Args:
            valid_actions: A list of valid column indices where a piece can be dropped.

        Returns:
            The chosen column index.
        """
        # Add a tiny delay so human observers can watch the game unfold
        await asyncio.sleep(0.5)
        
        self.valid_actions = valid_actions
        self.other_player_id = 2 if self.player_id == 1 else 1
        board_state = data.get("board")

        bitboard_me = 0
        bitboard_other = 0
        for row in range(6):
            for col in range(7):
                cell_value = board_state[row][col]
                if cell_value == self.player_id:
                    bitboard_me |= (1 << (row * 7 + col))
                elif cell_value != 0:
                    bitboard_other |= (1 << (row * 7 + col))

        print("Searching best move with Minimax...")
        chosen_col: int = self.choose_move(bitboard_me, bitboard_other)
        return chosen_col
    
    def choose_move(self, bitboard_me: int, bitboard_other: int) -> int:
        best_choice = random.choice(self.valid_actions)
        best_score = float('-inf')

        for col in self.valid_actions:
            new_bitboard = self.drop_piece(bitboard_me, bitboard_other, col, self.player_id)
            score = self.minimax(new_bitboard, bitboard_other, self.DEPTH_SEARCH, False)
            if score > best_score:
                best_score = score
                best_choice = col
        return best_choice
    
    def minimax(self, bitboard_me: int, bitboard_other: int, depth: int, maximizing_player: bool) -> int:
        if depth == 0:
            return self.evaluate_board(bitboard_me, bitboard_other)

        if maximizing_player:
            max_eval = float('-inf')
            for col in self.valid_actions:
                new_me = self.drop_piece(bitboard_me, bitboard_other, col, self.player_id)
                eval = self.minimax(new_me, bitboard_other, depth - 1, False)
                max_eval = max(max_eval, eval)
            return max_eval
        else:
            min_eval = float('inf')
            for col in self.valid_actions:
                new_other = self.drop_piece(bitboard_me, bitboard_other, col, self.other_player_id)  # Simulate opponent's move
                eval = self.minimax(bitboard_me, new_other, depth - 1, True)
                min_eval = min(min_eval, eval)
            return min_eval

    def evaluate_board(self, bitboard_me: int, bitboard_other: int) -> int:
        score = 0
        if self.check_win(bitboard_me):
            return 1000  # High score for winning positions
        elif self.check_win(bitboard_other):
            return -1000  # Low score for losing positions
        
        for row in range(6):
            for col in range(7):
                if (bitboard_me & (1 << (row * 7 + col))) != 0:
                    score += self.board_weights[row][col]
                elif (bitboard_other & (1 << (row * 7 + col))) != 0:
                    score -= self.board_weights[row][col]
        return score

    def drop_piece(self, bitboard_me, bitboard_other, col, player_id):
        combined = bitboard_me | bitboard_other
        
        # Start from the bottom row (5) and move up to the top (0)
        for row in range(5, -1, -1):
            mask = 1 << (row * 7 + col) # Bitmask for the current cell
            
            # If this specific cell is empty
            if not (combined & mask):
                # Return the updated bitboard for the specified player
                if player_id == self.player_id:
                    return bitboard_me | mask
                else:
                    return bitboard_other | mask
        
        # Column was full, no change
        if player_id == self.player_id:
            return bitboard_me
        else:
            return bitboard_other

    def check_win(self, bitboard):
        # Check horizontal, vertical, and diagonal (both directions) for a win
        directions = [1, 7, 6, 8]  # right, down, down-left, down-right
        for direction in directions:
            if (bitboard & (bitboard >> direction) & (bitboard >> (2 * direction)) & (bitboard >> (3 * direction))) != 0:
                return True
        return False
    
if __name__ == "__main__":
    agent = MinimaxAgent()
    asyncio.run(agent.run())
