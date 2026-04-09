import asyncio
import os
import sys
from typing import List, Optional

# Add the parent directory to sys.path to allow running agents as scripts from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import BaseC4Agent


class ManualC4Agent(BaseC4Agent):
    """
    A human-controlled agent using terminal inputs (0-6).
    """

    async def deliberate(self, valid_actions: List[int]) -> Optional[int]:
        """
        Asks the user to select a column from the list of valid actions.

        Args:
            valid_actions: A list of valid column indices where a piece can be dropped.

        Returns:
            The chosen column index.
        """
        print(f"\n--- YOUR TURN (Player {self.player_id}) ---")
        print(f"Valid columns: {valid_actions}")

        while True:
            # Use to_thread to prevent the asyncio loop from freezing
            user_input: str = await asyncio.to_thread(input, "Select column (0-6): ")

            try:
                col: int = int(user_input.strip())
                if col in valid_actions:
                    return col
                else:
                    print("Invalid column. Either it's full or out of bounds. Try again.")
            except ValueError:
                print("Invalid input. Please enter a number between 0 and 6.")


if __name__ == "__main__":
    agent = ManualC4Agent()
    print("Starting Manual Connect 4 Agent...")
    asyncio.run(agent.run())
