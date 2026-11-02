"""뱀 게임 (Snake Game) - tkinter 사용 (추가 설치 불필요)

조작법:
    방향키 / WASD : 이동
    P            : 일시정지 / 재개
    R            : 게임 오버 후 다시 시작
    ESC          : 종료
"""
import random
import tkinter as tk

# 설정
CELL = 20            # 한 칸 크기 (px)
COLS, ROWS = 30, 24  # 격자 크기
WIDTH, HEIGHT = COLS * CELL, ROWS * CELL
START_SPEED = 120    # 이동 간격 (ms), 작을수록 빠름
MIN_SPEED = 50

BG_COLOR = "#1e1e2e"
SNAKE_HEAD = "#a6e3a1"
SNAKE_BODY = "#40a02b"
FOOD_COLOR = "#f38ba8"
TEXT_COLOR = "#cdd6f4"

DIRECTIONS = {
    "Up": (0, -1), "w": (0, -1), "W": (0, -1),
    "Down": (0, 1), "s": (0, 1), "S": (0, 1),
    "Left": (-1, 0), "a": (-1, 0), "A": (-1, 0),
    "Right": (1, 0), "d": (1, 0), "D": (1, 0),
}


class SnakeGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Snake Game")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT,
                                bg=BG_COLOR, highlightthickness=0)
        self.canvas.pack()

        self.high_score = 0
        self.after_id = None
        root.bind("<Key>", self.on_key)
        self.reset()

    def reset(self):
        cx, cy = COLS // 2, ROWS // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.score = 0
        self.speed = START_SPEED
        self.game_over = False
        self.paused = False
        self.food = self.spawn_food()
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.tick()

    def spawn_food(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in self.snake]
        return random.choice(free) if free else None

    def on_key(self, event):
        key = event.keysym
        if key == "Escape":
            self.root.destroy()
        elif key in ("p", "P") and not self.game_over:
            self.paused = not self.paused
            self.draw()
        elif key in ("r", "R") and self.game_over:
            self.reset()
        elif key in DIRECTIONS:
            dx, dy = DIRECTIONS[key]
            # 반대 방향으로는 바로 돌 수 없음
            if (dx, dy) != (-self.direction[0], -self.direction[1]):
                self.next_direction = (dx, dy)

    def tick(self):
        if not self.game_over and not self.paused:
            self.step()
        self.draw()
        self.after_id = self.root.after(self.speed, self.tick)

    def step(self):
        self.direction = self.next_direction
        hx, hy = self.snake[0]
        new_head = (hx + self.direction[0], hy + self.direction[1])

        # 벽 또는 자기 몸에 충돌 (꼬리는 이번 턴에 이동하므로 제외)
        body = self.snake[:-1] if new_head != self.food else self.snake
        if (not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS)
                or new_head in body):
            self.game_over = True
            self.high_score = max(self.high_score, self.score)
            return

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 10
            self.speed = max(MIN_SPEED, self.speed - 3)
            self.food = self.spawn_food()
            if self.food is None:  # 화면을 다 채움 = 승리
                self.game_over = True
                self.high_score = max(self.high_score, self.score)
        else:
            self.snake.pop()

    def draw(self):
        c = self.canvas
        c.delete("all")

        if self.food:
            fx, fy = self.food
            c.create_oval(fx * CELL + 3, fy * CELL + 3,
                          (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
                          fill=FOOD_COLOR, outline="")

        for i, (x, y) in enumerate(self.snake):
            c.create_rectangle(x * CELL + 1, y * CELL + 1,
                               (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                               fill=SNAKE_HEAD if i == 0 else SNAKE_BODY,
                               outline="")

        c.create_text(10, 10, anchor="nw", fill=TEXT_COLOR,
                      font=("Consolas", 12, "bold"),
                      text=f"Score: {self.score}   Best: {self.high_score}")

        if self.paused:
            c.create_text(WIDTH / 2, HEIGHT / 2, fill=TEXT_COLOR,
                          font=("Consolas", 28, "bold"), text="PAUSED")
        elif self.game_over:
            c.create_text(WIDTH / 2, HEIGHT / 2 - 20, fill=FOOD_COLOR,
                          font=("Consolas", 32, "bold"), text="GAME OVER")
            c.create_text(WIDTH / 2, HEIGHT / 2 + 25, fill=TEXT_COLOR,
                          font=("Consolas", 14),
                          text=f"점수: {self.score}  |  R: 다시 시작  ESC: 종료")


if __name__ == "__main__":
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()
