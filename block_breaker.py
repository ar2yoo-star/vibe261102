import tkinter as tk


WIDTH = 800
HEIGHT = 600
PADDLE_WIDTH = 110
PADDLE_HEIGHT = 14
BALL_SIZE = 16
BRICK_ROWS = 5
BRICK_COLUMNS = 10
BRICK_WIDTH = 68
BRICK_HEIGHT = 22
BRICK_GAP = 7


class BlockBreaker:
    def __init__(self, root):
        self.root = root
        self.root.title("블록깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg="#101820",
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.focus_set()

        self.keys = set()
        self.score = 0
        self.lives = 3
        self.state = "ready"
        self.ball_dx = 4
        self.ball_dy = -4

        self.canvas.bind("<KeyPress>", self.on_key_press)
        self.canvas.bind("<KeyRelease>", self.on_key_release)

        self.draw_hud()
        self.create_paddle()
        self.create_ball()
        self.create_bricks()
        self.show_message("스페이스를 눌러 시작")
        self.game_loop()

    def draw_hud(self):
        self.score_text = self.canvas.create_text(
            20, 18, anchor="nw", fill="white", font=("맑은 고딕", 14, "bold")
        )
        self.lives_text = self.canvas.create_text(
            WIDTH - 20,
            18,
            anchor="ne",
            fill="white",
            font=("맑은 고딕", 14, "bold"),
        )
        self.canvas.tag_bind("pause_button", "<Button-1>", self.on_pause_button_click)
        self.canvas.tag_bind("pause_button", "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("pause_button", "<Leave>", lambda _event: self.canvas.configure(cursor=""))
        self.update_hud()
        self.draw_pause_button()

    def draw_pause_button(self):
        self.canvas.delete("pause_button")
        center_x = WIDTH / 2
        self.canvas.create_rectangle(
            center_x - 19,
            8,
            center_x + 19,
            46,
            fill="#263746",
            outline="#8aa1ad",
            width=1,
            tags="pause_button",
        )

        if self.state == "playing":
            self.canvas.create_rectangle(
                center_x - 8, 18, center_x - 3, 36,
                fill="white", outline="", tags="pause_button"
            )
            self.canvas.create_rectangle(
                center_x + 3, 18, center_x + 8, 36,
                fill="white", outline="", tags="pause_button"
            )
        else:
            self.canvas.create_polygon(
                center_x - 5, 17, center_x - 5, 37, center_x + 10, 27,
                fill="white", outline="", tags="pause_button"
            )

    def set_state(self, state):
        self.state = state
        self.draw_pause_button()

    def on_pause_button_click(self, _event):
        if self.state == "playing":
            self.set_state("paused")
            self.show_message("일시정지  ·  아이콘 또는 P를 눌러 계속")
        elif self.state == "paused":
            self.set_state("playing")
            self.canvas.delete("message")
        elif self.state in ("ready", "won", "lost"):
            if self.state in ("won", "lost"):
                self.reset_game()
            self.set_state("playing")
            self.canvas.delete("message")

    def update_hud(self):
        self.canvas.itemconfigure(self.score_text, text=f"점수: {self.score}")
        self.canvas.itemconfigure(self.lives_text, text=f"목숨: {self.lives}")

    def create_paddle(self):
        x1 = (WIDTH - PADDLE_WIDTH) / 2
        y1 = HEIGHT - 55
        self.paddle = self.canvas.create_rectangle(
            x1,
            y1,
            x1 + PADDLE_WIDTH,
            y1 + PADDLE_HEIGHT,
            fill="#40c4aa",
            outline="",
        )

    def create_ball(self):
        x1, y1, x2, y2 = self.canvas.coords(self.paddle)
        center_x = (x1 + x2) / 2
        self.ball = self.canvas.create_oval(
            center_x - BALL_SIZE / 2,
            y1 - BALL_SIZE - 2,
            center_x + BALL_SIZE / 2,
            y1 - 2,
            fill="#ffd166",
            outline="",
        )

    def create_bricks(self):
        colors = ["#ef476f", "#f78c6b", "#ffd166", "#06d6a0", "#118ab2"]
        total_width = BRICK_COLUMNS * BRICK_WIDTH + (BRICK_COLUMNS - 1) * BRICK_GAP
        start_x = (WIDTH - total_width) / 2
        start_y = 78

        for row in range(BRICK_ROWS):
            for column in range(BRICK_COLUMNS):
                x1 = start_x + column * (BRICK_WIDTH + BRICK_GAP)
                y1 = start_y + row * (BRICK_HEIGHT + BRICK_GAP)
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x1 + BRICK_WIDTH,
                    y1 + BRICK_HEIGHT,
                    fill=colors[row],
                    outline="",
                    tags="brick",
                )

    def show_message(self, message):
        self.canvas.delete("message")
        self.canvas.create_text(
            WIDTH / 2,
            HEIGHT / 2,
            text=message,
            fill="white",
            font=("맑은 고딕", 22, "bold"),
            tags="message",
        )

    def on_key_press(self, event):
        if event.keysym in ("Left", "Right"):
            self.keys.add(event.keysym)
        elif event.keysym.lower() == "p" and "p" not in self.keys:
            self.keys.add("p")
            if self.state == "playing":
                self.set_state("paused")
                self.show_message("일시정지  ·  아이콘 또는 P를 눌러 계속")
            elif self.state == "paused":
                self.set_state("playing")
                self.canvas.delete("message")
        elif event.keysym == "space":
            if self.state in ("won", "lost"):
                self.reset_game()
            if self.state == "ready":
                self.set_state("playing")
                self.canvas.delete("message")

    def on_key_release(self, event):
        self.keys.discard(event.keysym)
        self.keys.discard(event.keysym.lower())

    def reset_ball(self):
        x1, y1, x2, _ = self.canvas.coords(self.paddle)
        center_x = (x1 + x2) / 2
        self.canvas.coords(
            self.ball,
            center_x - BALL_SIZE / 2,
            y1 - BALL_SIZE - 2,
            center_x + BALL_SIZE / 2,
            y1 - 2,
        )
        self.ball_dx = 4
        self.ball_dy = -4

    def reset_game(self):
        self.canvas.delete("brick")
        self.score = 0
        self.lives = 3
        self.set_state("ready")
        self.update_hud()
        self.canvas.coords(self.paddle, (WIDTH - PADDLE_WIDTH) / 2, HEIGHT - 55,
                           (WIDTH + PADDLE_WIDTH) / 2, HEIGHT - 55 + PADDLE_HEIGHT)
        self.create_bricks()
        self.reset_ball()
        self.show_message("스페이스를 눌러 시작")

    def move_paddle(self):
        dx = 0
        if "Left" in self.keys:
            dx -= 7
        if "Right" in self.keys:
            dx += 7
        if dx == 0:
            return

        x1, _, x2, _ = self.canvas.coords(self.paddle)
        dx = max(-x1, min(dx, WIDTH - x2))
        self.canvas.move(self.paddle, dx, 0)
        if self.state == "ready":
            self.reset_ball()

    def move_ball(self):
        self.canvas.move(self.ball, self.ball_dx, self.ball_dy)
        bx1, by1, bx2, by2 = self.canvas.coords(self.ball)

        if bx1 <= 0 or bx2 >= WIDTH:
            self.ball_dx *= -1
        if by1 <= 0:
            self.ball_dy = abs(self.ball_dy)

        px1, py1, px2, _ = self.canvas.coords(self.paddle)
        if (
            self.ball_dy > 0
            and by2 >= py1
            and by1 <= py1 + PADDLE_HEIGHT
            and bx2 >= px1
            and bx1 <= px2
        ):
            hit_position = ((bx1 + bx2) / 2 - (px1 + px2) / 2) / (PADDLE_WIDTH / 2)
            self.ball_dx = hit_position * 5
            self.ball_dy = -abs(self.ball_dy)

        self.check_brick_collision()

        if by2 >= HEIGHT:
            self.lives -= 1
            self.update_hud()
            if self.lives <= 0:
                self.set_state("lost")
                self.show_message("게임 오버  ·  스페이스를 눌러 다시 시작")
            else:
                self.set_state("ready")
                self.reset_ball()
                self.show_message("스페이스를 눌러 계속")

    def check_brick_collision(self):
        bx1, by1, bx2, by2 = self.canvas.coords(self.ball)
        overlapping = self.canvas.find_overlapping(bx1, by1, bx2, by2)
        brick_items = [item for item in overlapping if "brick" in self.canvas.gettags(item)]

        if not brick_items:
            return

        brick = brick_items[0]
        rx1, ry1, rx2, ry2 = self.canvas.coords(brick)
        overlap_x = min(bx2 - rx1, rx2 - bx1)
        overlap_y = min(by2 - ry1, ry2 - by1)
        if overlap_x < overlap_y:
            self.ball_dx *= -1
        else:
            self.ball_dy *= -1

        self.canvas.delete(brick)
        self.score += 10
        self.update_hud()

        if not self.canvas.find_withtag("brick"):
            self.set_state("won")
            self.show_message("승리!  ·  스페이스를 눌러 다시 시작")

    def game_loop(self):
        if self.state in ("ready", "playing"):
            self.move_paddle()
        if self.state == "playing":
            self.move_ball()
        self.root.after(16, self.game_loop)


if __name__ == "__main__":
    window = tk.Tk()
    game = BlockBreaker(window)
    window.mainloop()