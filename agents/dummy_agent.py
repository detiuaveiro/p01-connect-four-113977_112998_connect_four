import asyncio
import os
import random
import sys
from typing import List, Optional

# Add the parent directory to sys.path to allow running agents as scripts from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseC4Agent


class DummyC4Agent(BaseC4Agent):
    """
    A completely random agent for Connect Four.
    """

    async def deliberate(self, valid_actions: List[int]) -> Optional[int]:
        """
        Picks a random valid column after a brief delay.

        Args:
            valid_actions: A list of valid column indices where a piece can be dropped.

        Returns:
            The chosen column index.
        """
        # Add a tiny delay so human observers can watch the game unfold
        await asyncio.sleep(0.5)

        # Pick a random valid column
        chosen_col: int = random.choice(valid_actions)
        return chosen_col


if __name__ == "__main__":
    agent = DummyC4Agent()
    asyncio.run(agent.run())
