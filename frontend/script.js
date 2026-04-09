class App {
  constructor() {
    const serverHost = window.location.hostname;
    this.ws = new WebSocket(`ws://${serverHost}:8765`);
    this.canvas = document.getElementById("sim-canvas");
    this.ctx = this.canvas.getContext("2d");

    this.cols = 7;
    this.rows = 6;
    this.cellSize = 100;

    this.board = null;
    this.setupWebsocket();
    this.drawEmptyBoard();
  }

  setupWebsocket() {
    this.ws.onopen = () => this.ws.send(JSON.stringify({ client: "frontend" }));

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "update") {
        this.board = data.board;

        // Update UI Status
        document.getElementById("p1-status").innerText = data.p1_connected
          ? "Player 1 (Red): Connected"
          : "Player 1 (Red): Disconnected";
        document.getElementById("p2-status").innerText = data.p2_connected
          ? "Player 2 (Yellow): Connected"
          : "Player 2 (Yellow): Disconnected";
        document.getElementById("p1-score").innerText = data.scores[1];
        document.getElementById("p2-score").innerText = data.scores[2];

        const turnText = document.getElementById("turn-indicator");
        if (data.p1_connected && data.p2_connected) {
          turnText.innerText = `Current Turn: Player ${data.current_turn}`;
          turnText.style.color =
            data.current_turn === 1 ? "#BF616A" : "#EBCB8B";
        } else {
          turnText.innerText = "Waiting for agents...";
          turnText.style.color = "#D8DEE9";
        }

        // Handle Game Over Message
        const overlay = document.getElementById("message-overlay");
        const message = document.getElementById("game-message");
        if (data.game_over) {
          message.innerText = data.game_over;
          overlay.classList.remove("hidden");
        } else {
          overlay.classList.add("hidden");
        }

        this.draw();
      }
    };
  }

  drawEmptyBoard() {
    this.ctx.fillStyle = "#2E3440";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
  }

  draw() {
    if (!this.board) return;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Draw the classic blue plastic board
    this.ctx.fillStyle = "#5E81AC";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const centerX = c * this.cellSize + this.cellSize / 2;
        const centerY = r * this.cellSize + this.cellSize / 2;
        const radius = this.cellSize / 2.5;

        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);

        // Fill holes based on state
        if (this.board[r][c] === 1) {
          this.ctx.fillStyle = "#BF616A"; // Nord Red
        } else if (this.board[r][c] === 2) {
          this.ctx.fillStyle = "#EBCB8B"; // Nord Yellow
        } else {
          this.ctx.fillStyle = "#2E3440"; // Empty (Background color showing through)
        }
        this.ctx.fill();

        // Add inner shadow to holes to make the board look 3D
        this.ctx.lineWidth = 4;
        this.ctx.strokeStyle = "rgba(0,0,0,0.2)";
        this.ctx.stroke();
      }
    }
  }
}
const app = new App();
