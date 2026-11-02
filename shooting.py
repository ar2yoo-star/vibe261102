"""종스크롤 슈팅 게임 - Sky Striker (pygame)

조작
  방향키 / WASD : 이동
  Space / Z     : 발사 (누르고 있으면 연사)
  X             : 폭탄 (화면의 적 탄 제거 + 전체 공격)
  P             : 일시정지
  M             : 소리 켜기/끄기
  Enter         : 시작 / 재시작
  Esc           : 종료

P 아이템을 먹을 때마다 발사 수가 2 -> 4 -> 8 -> 16발로 늘어납니다.
효과음은 외부 파일 없이 코드로 직접 합성합니다.

실행: pip install pygame  후  python shooting.py
"""
import math
import random
import sys
from array import array

import pygame

WIDTH, HEIGHT = 480, 720
FPS = 60
TILE = 40
COLS = WIDTH // TILE
SCROLL_SPEED = 1.2
BOSS_INTERVAL = 45 * FPS  # 스테이지 시작 후 보스 등장까지 걸리는 프레임

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (255, 230, 90)
ORANGE = (255, 150, 40)
RED = (235, 60, 60)
CYAN = (90, 220, 255)
FIRE_COLORS = [(255, 240, 150), (255, 190, 60), (255, 120, 40), (200, 60, 30)]


def load_font(size, bold=False):
    """한글이 나오는 시스템 폰트를 찾고, 없으면 기본 폰트를 사용"""
    for name in ("malgungothic", "applegothic", "nanumgothic", "notosanscjkkr"):
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size + 8)


def draw_text(surf, font, text, color, pos, anchor="center", shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(font.render(text, True, BLACK), rect.move(2, 2))
    surf.blit(img, rect)
    return rect


# ---------------------------------------------------------------- 사운드

class SoundBank:
    """파형을 직접 계산해서 효과음을 만듦. 사운드 장치가 없으면 조용히 무음으로 동작"""

    def __init__(self):
        self.sounds = {}
        self.muted = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, size, self.channels = pygame.mixer.get_init()
        except pygame.error:
            return
        if size != -16:
            return
        pygame.mixer.set_num_channels(24)

        self.sounds = {
            "shoot": self._make(self._tone(0.06, 1400, 500, decay=1.5), 0.10),
            "hit": self._make(self._tone(0.03, 300, 200, "none", noise=1.0, decay=1.0), 0.15),
            "explode": self._make(self._tone(0.35, 140, 60, "sine", noise=0.8, lowpass=0.25, decay=2.0), 0.55),
            "big_explode": self._make(self._tone(1.0, 90, 30, "sine", noise=0.85, lowpass=0.08, decay=1.6), 0.8),
            "powerup": self._make(self._notes([523, 659, 784, 1047, 1319], 0.055, "square"), 0.22),
            "item": self._make(self._notes([784, 1175], 0.07, "tri"), 0.35),
            "bomb": self._make(self._tone(0.9, 420, 50, "square", noise=0.5, lowpass=0.1, decay=1.2), 0.5),
            "player_die": self._make(self._tone(0.8, 900, 80, "square", noise=0.4, lowpass=0.3, decay=1.0), 0.4),
            "warning": self._make(self._notes([880, 660] * 3, 0.14, "square", decay=0.3), 0.25),
            "stage": self._make(self._notes([523, 659, 784, 659, 784, 1047], 0.09, "tri"), 0.35),
        }

    def play(self, name):
        sound = self.sounds.get(name)
        if sound and not self.muted:
            sound.play()

    def _tone(self, duration, f0, f1, wave="square", noise=0.0, lowpass=0.0, decay=2.0, seed=1):
        """f0 -> f1 으로 주파수가 변하는 파형 + 노이즈, 끝으로 갈수록 작아지는 엔벨로프"""
        rnd = random.Random(seed)
        n = int(self.rate * duration)
        out = []
        phase = 0.0
        filtered = 0.0
        for i in range(n):
            p = i / n
            phase += (f0 + (f1 - f0) * p) / self.rate
            if wave == "square":
                s = 1.0 if phase % 1 < 0.5 else -1.0
            elif wave == "tri":
                s = 4 * abs(phase % 1 - 0.5) - 1
            elif wave == "sine":
                s = math.sin(phase * math.tau)
            else:
                s = 0.0
            if noise:
                nz = rnd.uniform(-1, 1)
                if lowpass:  # 간단한 1차 저역 필터 -> 둔탁한 폭발음
                    filtered += (nz - filtered) * lowpass
                    nz = filtered / math.sqrt(lowpass)
                s = s * (1 - noise) + nz * noise
            out.append(s * (1 - p) ** decay)
        return out

    def _notes(self, freqs, note_duration, wave, decay=0.6):
        out = []
        for f in freqs:
            out += self._tone(note_duration, f, f, wave, decay=decay)
        return out

    def _make(self, samples, volume):
        frames = array("h")
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * volume * 32767)
            frames.extend([v] * self.channels)
        return pygame.mixer.Sound(buffer=frames.tobytes())


# ---------------------------------------------------------------- 배경

def make_tile_surfaces():
    rnd = random.Random(7)
    tiles = {}

    def base(color, speckle, count):
        s = pygame.Surface((TILE, TILE))
        s.fill(color)
        for _ in range(count):
            s.fill(speckle, (rnd.randrange(TILE), rnd.randrange(TILE), 2, 2))
        return s

    tiles["grass"] = base((58, 112, 54), (72, 132, 64), 18)

    forest = base((48, 96, 46), (60, 110, 56), 6)
    for _ in range(4):
        x, y = rnd.randint(8, 32), rnd.randint(8, 32)
        pygame.draw.circle(forest, (30, 68, 34), (x + 2, y + 3), 9)
        pygame.draw.circle(forest, (42, 96, 44), (x, y), 9)
        pygame.draw.circle(forest, (66, 128, 62), (x - 3, y - 3), 4)
    tiles["forest"] = forest

    tiles["sand"] = base((196, 178, 120), (176, 158, 104), 20)

    for i in range(2):
        water = pygame.Surface((TILE, TILE))
        water.fill((40, 90, 160))
        for _ in range(5):
            x, y = rnd.randrange(TILE - 10), rnd.randrange(TILE)
            pygame.draw.line(water, (80, 140, 210), (x, y), (x + 8, y), 1)
        tiles[f"water{i}"] = water

    road = base((92, 92, 98), (80, 80, 86), 10)
    pygame.draw.line(road, (225, 210, 110), (8, TILE // 2), (TILE - 8, TILE // 2), 2)
    tiles["road"] = road

    bridge = pygame.Surface((TILE, TILE))
    bridge.fill((130, 92, 58))
    for x in range(0, TILE, 8):
        pygame.draw.line(bridge, (98, 66, 40), (x, 0), (x, TILE), 2)
    pygame.draw.line(bridge, (70, 50, 30), (0, 2), (TILE, 2), 3)
    pygame.draw.line(bridge, (70, 50, 30), (0, TILE - 3), (TILE, TILE - 3), 3)
    tiles["bridge"] = bridge
    return tiles


class Background:
    """타일 줄을 위에서 생성해 아래로 흘려보내는 종스크롤 지형"""

    def __init__(self, tiles):
        self.tiles = tiles
        self.river_x = COLS / 2
        self.river_w = 2.5
        self.rows_since_road = 0
        self.offset = 0.0
        self.anim = 0
        self.rows = [self._gen_row() for _ in range(HEIGHT // TILE + 2)]

    def _gen_row(self):
        # 강이 좌우로 구불구불 흐르도록 중심과 폭을 조금씩 바꿈
        self.river_x = min(max(self.river_x + random.uniform(-0.5, 0.5), 1.5), COLS - 1.5)
        self.river_w = min(max(self.river_w + random.uniform(-0.3, 0.3), 1.5), 4.0)
        self.rows_since_road += 1
        road = self.rows_since_road > 18 and random.random() < 0.15
        if road:
            self.rows_since_road = 0

        row = []
        for c in range(COLS):
            d = abs(c + 0.5 - self.river_x)
            if d < self.river_w / 2:
                row.append("bridge" if road else "water")
            elif road:
                row.append("road")
            elif d < self.river_w / 2 + 0.8:
                row.append("sand")
            else:
                row.append("forest" if random.random() < 0.18 else "grass")
        return row

    def update(self):
        """스크롤하고, 새 줄이 생기면 그 줄을 반환"""
        self.anim += 1
        self.offset += SCROLL_SPEED
        if self.offset >= TILE:
            self.offset -= TILE
            self.rows.pop()
            row = self._gen_row()
            self.rows.insert(0, row)
            return row
        return None

    def row_center_y(self, index):
        return -TILE + self.offset + index * TILE + TILE / 2

    def draw(self, surf):
        water = f"water{(self.anim // 30) % 2}"
        for i, row in enumerate(self.rows):
            y = int(-TILE + self.offset + i * TILE)
            for c, kind in enumerate(row):
                surf.blit(self.tiles[water if kind == "water" else kind], (c * TILE, y))


def make_cloud_image():
    img = pygame.Surface((180, 90), pygame.SRCALPHA)
    for x, y, r in ((50, 50, 30), (85, 40, 38), (125, 52, 30), (95, 60, 30)):
        pygame.draw.circle(img, (255, 255, 255, 70), (x, y), r)
    return img


class Cloud:
    def __init__(self, image, y=None):
        self.image = image
        self.x = random.uniform(-80, WIDTH - 100)
        self.y = random.uniform(-HEIGHT, HEIGHT) if y is None else y
        self.speed = random.uniform(2.2, 3.2)

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.x = random.uniform(-80, WIDTH - 100)
            self.y = random.uniform(-400, -100)

    def draw(self, surf):
        surf.blit(self.image, (int(self.x), int(self.y)))


# ---------------------------------------------------------------- 탄 / 이펙트 / 아이템

class Bullet:
    def __init__(self, x, y, vx, vy, friendly, radius=4, damage=1):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.friendly = friendly
        self.radius = radius
        self.damage = damage
        self.dead = False

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.x < -20 or self.x > WIDTH + 20 or self.y < -20 or self.y > HEIGHT + 20:
            self.dead = True

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.friendly:
            pygame.draw.rect(surf, (255, 240, 120), (x - 2, y - 8, 4, 16), border_radius=2)
            pygame.draw.rect(surf, WHITE, (x - 1, y - 6, 2, 10))
        else:
            pygame.draw.circle(surf, (255, 80, 120), (x, y), self.radius + 1)
            pygame.draw.circle(surf, (255, 220, 230), (x, y), self.radius - 1)


class Particle:
    def __init__(self, x, y, color, speed=3.0, life=30, size=3.0):
        angle = random.uniform(0, math.tau)
        spd = random.uniform(0.3, 1.0) * speed
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * spd, math.sin(angle) * spd
        self.color = color
        self.life = self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1

    def draw(self, surf):
        r = self.size * self.life / self.max_life
        if r >= 0.5:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), max(1, int(r)))


class Shockwave:
    def __init__(self, x, y, max_radius=60, life=20):
        self.x, self.y = x, y
        self.max_radius = max_radius
        self.life = self.max_life = life

    def update(self):
        self.life -= 1

    def draw(self, surf):
        progress = 1 - self.life / self.max_life
        r = int(self.max_radius * progress)
        if r > 2:
            pygame.draw.circle(surf, (255, 230, 180), (int(self.x), int(self.y)), r,
                               max(1, int(4 * (1 - progress))))


class PowerUp:
    COLORS = {"P": (255, 110, 60), "B": (80, 170, 255)}

    def __init__(self, x, y, kind):
        self.x, self.y = x, y
        self.kind = kind
        self.t = random.randint(0, 100)
        self.dead = False

    def update(self):
        self.t += 1
        self.y += 1.4
        self.x += math.sin(self.t * 0.06) * 0.8
        if self.y > HEIGHT + 20:
            self.dead = True

    def draw(self, surf, font):
        x, y = int(self.x), int(self.y)
        r = 12 + int(math.sin(self.t * 0.2) * 2)
        pygame.draw.circle(surf, self.COLORS[self.kind], (x, y), r)
        pygame.draw.circle(surf, WHITE, (x, y), r, 2)
        draw_text(surf, font, self.kind, WHITE, (x, y), shadow=False)


# ---------------------------------------------------------------- 플레이어

class Player:
    SPEED = 4.6
    MAX_POWER = 4  # 파워 1~4 -> 2, 4, 8, 16발
    # 파워별 좌우 탄 사이의 벌어짐 각도 (값이 클수록 넓게 퍼짐)
    SPREAD_STEP = {1: 0.0, 2: 0.12, 3: 0.09, 4: 0.065}

    def __init__(self):
        self.x, self.y = WIDTH / 2, HEIGHT - 110
        self.radius = 5  # 피격 판정 (기체보다 작게)
        self.cooldown = 0
        self.power = 1
        self.bombs = 3
        self.invuln = 120
        self.t = 0

    def respawn(self):
        self.x, self.y = WIDTH / 2, HEIGHT - 110
        self.invuln = 150
        self.bombs = max(self.bombs, 2)

    def update(self, keys, game):
        self.t += 1
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        speed = self.SPEED / math.sqrt(2) if dx and dy else self.SPEED
        self.x = min(max(self.x + dx * speed, 18), WIDTH - 18)
        self.y = min(max(self.y + dy * speed, 24), HEIGHT - 24)

        if self.invuln:
            self.invuln -= 1
        if self.cooldown:
            self.cooldown -= 1
        if (keys[pygame.K_SPACE] or keys[pygame.K_z]) and not self.cooldown:
            self.fire(game)
            self.cooldown = 7

    @property
    def shot_count(self):
        return 2 ** self.power

    def fire(self, game):
        # 좌우 대칭으로 한 쌍씩 쏘고, 바깥쪽 쌍일수록 더 벌어지게 함
        step = self.SPREAD_STEP[self.power]
        for i in range(self.shot_count // 2):
            ox = 5 + i * 2
            angle = i * step
            for side in (-1, 1):
                game.player_bullets.append(
                    Bullet(self.x + side * ox, self.y - 14,
                           math.sin(side * angle) * 11, -math.cos(angle) * 11, True))
        game.sfx.play("shoot")

    def draw(self, surf):
        if self.invuln and (self.invuln // 4) % 2:
            return
        x, y = self.x, self.y
        flame = 8 + (self.t % 6)
        pygame.draw.polygon(surf, ORANGE, [(x - 4, y + 13), (x + 4, y + 13), (x, y + 13 + flame)])
        pygame.draw.polygon(surf, YELLOW, [(x - 2, y + 13), (x + 2, y + 13), (x, y + 9 + flame)])
        body = [(0, -20), (6, -6), (18, 6), (18, 11), (6, 8), (5, 14), (-5, 14), (-6, 8),
                (-18, 11), (-18, 6), (-6, -6)]
        pts = [(x + px, y + py) for px, py in body]
        pygame.draw.polygon(surf, (200, 210, 225), pts)
        pygame.draw.polygon(surf, (90, 100, 130), pts, 2)
        pygame.draw.ellipse(surf, CYAN, (x - 3, y - 10, 6, 11))


# ---------------------------------------------------------------- 적

class Enemy:
    radius = 14
    hp = 1
    score = 100
    ground = False       # 지상 유닛은 몸통 충돌이 없음
    drop_chance = 0.04

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.t = 0
        self.flash = 0
        self.dead = False

    def hit(self, damage):
        self.hp -= damage
        self.flash = 4

    def update(self, game):
        self.t += 1
        if self.flash:
            self.flash -= 1
        self.move(game)

    def move(self, game):
        pass

    def offscreen(self):
        return self.y > HEIGHT + 60 or self.y < -240 or self.x < -100 or self.x > WIDTH + 100

    def color(self, normal):
        return WHITE if self.flash else normal


class Dart(Enemy):
    """좌우로 흔들리며 내려오는 소형기"""
    radius = 13
    score = 100

    def __init__(self, x, y):
        super().__init__(x, y)
        self.base_x = x
        self.phase = random.uniform(0, math.tau)
        self.fire_at = random.randint(30, 110)

    def move(self, game):
        self.y += 3.2
        self.x = self.base_x + math.sin(self.t * 0.05 + self.phase) * 30
        if self.t == self.fire_at and 0 < self.y < HEIGHT * 0.6:
            game.shoot_at(self.x, self.y, 4.0)

    def draw(self, surf):
        x, y = self.x, self.y
        pts = [(x, y + 14), (x + 14, y - 8), (x + 5, y - 4), (x, y - 12), (x - 5, y - 4), (x - 14, y - 8)]
        pygame.draw.polygon(surf, self.color((210, 60, 70)), pts)
        pygame.draw.polygon(surf, (110, 20, 30), pts, 2)
        pygame.draw.circle(surf, YELLOW, (int(x), int(y)), 3)


class Swooper(Enemy):
    """화면 옆에서 들어와 곡선을 그리며 지나가는 편대기"""
    radius = 12
    score = 150

    def __init__(self, x, y, direction):
        super().__init__(x, y)
        self.dir = direction  # +1: 왼쪽에서 등장, -1: 오른쪽에서 등장
        self.angle = math.pi / 2 - direction * 1.0

    def move(self, game):
        if self.t < 120:
            self.angle += self.dir * 0.018
        self.x += math.cos(self.angle) * 3.6
        self.y += math.sin(self.angle) * 3.6
        if self.t == 45:
            game.shoot_at(self.x, self.y, 3.6)

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        pygame.draw.circle(surf, self.color((160, 90, 220)), (x, y), 12)
        pygame.draw.circle(surf, (70, 30, 120), (x, y), 12, 2)
        a = self.t * 0.25
        for k in range(3):
            ang = a + k * math.tau / 3
            pygame.draw.line(surf, (230, 200, 255), (x, y),
                             (x + math.cos(ang) * 10, y + math.sin(ang) * 10), 2)
        pygame.draw.circle(surf, WHITE, (x, y), 3)


class Gunship(Enemy):
    """내려와서 잠시 머물며 확산탄을 쏘는 중형기"""
    radius = 24
    hp = 14
    score = 500
    drop_chance = 0.4

    def __init__(self, x, y):
        super().__init__(x, y)
        self.target_y = random.uniform(90, 220)
        self.base_x = x

    def move(self, game):
        if self.t < 260:
            self.y += (self.target_y - self.y) * 0.04
            self.x = self.base_x + math.sin(self.t * 0.03) * 40
            if self.t > 50 and self.t % 45 == 0:
                aim = game.angle_to_player(self.x, self.y)
                for k in range(-2, 3):
                    game.enemy_shot(self.x, self.y + 16, aim + k * 0.22, 3.4)
        else:
            self.y += 2.6

    def draw(self, surf):
        x, y = self.x, self.y
        hull = [(x - 26, y - 6), (x - 10, y - 18), (x + 10, y - 18), (x + 26, y - 6),
                (x + 18, y + 14), (x - 18, y + 14)]
        pygame.draw.polygon(surf, self.color((80, 110, 90)), hull)
        pygame.draw.polygon(surf, (30, 50, 40), hull, 2)
        pygame.draw.rect(surf, (50, 60, 55), (x - 4, y + 8, 8, 14))
        pygame.draw.circle(surf, self.color((240, 90, 60)), (int(x), int(y - 2)), 7)


class Turret(Enemy):
    """지형과 함께 스크롤되며 플레이어를 조준하는 지상 포대"""
    radius = 15
    hp = 5
    score = 200
    ground = True
    drop_chance = 0.12

    def __init__(self, x, y):
        super().__init__(x, y)
        self.aim = math.pi / 2
        self.cool = random.randint(50, 110)

    def move(self, game):
        self.y += SCROLL_SPEED
        self.aim = game.angle_to_player(self.x, self.y)
        self.cool -= 1
        if self.cool <= 0 and 20 < self.y < HEIGHT - 220:
            game.enemy_shot(self.x + math.cos(self.aim) * 18, self.y + math.sin(self.aim) * 18,
                            self.aim, 3.0)
            self.cool = random.randint(90, 150)

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        pygame.draw.rect(surf, (70, 70, 76), (x - 16, y - 16, 32, 32), border_radius=4)
        pygame.draw.rect(surf, (40, 40, 46), (x - 16, y - 16, 32, 32), 2, border_radius=4)
        end = (x + math.cos(self.aim) * 20, y + math.sin(self.aim) * 20)
        pygame.draw.line(surf, (30, 30, 34), (x, y), end, 6)
        pygame.draw.circle(surf, self.color((150, 150, 160)), (x, y), 10)
        pygame.draw.circle(surf, (200, 60, 60), (x, y), 4)


class Boss(Enemy):
    radius = 50
    score = 5000
    drop_chance = 0

    def __init__(self, stage):
        super().__init__(WIDTH / 2, -110)
        self.max_hp = 160 + stage * 60
        self.hp = self.max_hp
        self.spin = 0.0

    def offscreen(self):
        return False

    def move(self, game):
        if self.y < 140:
            self.y += 1.4
            self.t = 0  # 등장이 끝난 뒤부터 공격 패턴 시작
            return
        self.x = WIDTH / 2 + math.sin(self.t * 0.012) * 140
        phase = (self.t // 240) % 3
        if phase == 0 and self.t % 8 == 0:        # 회전 나선탄
            for k in range(4):
                game.enemy_shot(self.x, self.y, self.spin + k * math.tau / 4, 3.0)
            self.spin += 0.23
        elif phase == 1 and self.t % 50 == 0:     # 원형 탄막
            offset = random.uniform(0, math.tau)
            for k in range(18):
                game.enemy_shot(self.x, self.y, offset + k * math.tau / 18, 2.8)
        elif phase == 2 and self.t % 26 == 0:     # 양쪽 포대에서 조준 3연발
            for side in (-40, 40):
                aim = game.angle_to_player(self.x + side, self.y + 20)
                for k in (-0.15, 0, 0.15):
                    game.enemy_shot(self.x + side, self.y + 20, aim + k, 4.2)

    def draw(self, surf):
        x, y = self.x, self.y
        wing = [(x - 90, y + 4), (x - 50, y - 26), (x + 50, y - 26), (x + 90, y + 4),
                (x + 60, y + 24), (x - 60, y + 24)]
        pygame.draw.polygon(surf, self.color((70, 80, 110)), wing)
        pygame.draw.polygon(surf, (30, 35, 55), wing, 3)
        hull = [(x - 34, y - 44), (x + 34, y - 44), (x + 46, y + 10), (x + 20, y + 44),
                (x - 20, y + 44), (x - 46, y + 10)]
        pygame.draw.polygon(surf, self.color((110, 120, 150)), hull)
        pygame.draw.polygon(surf, (40, 45, 70), hull, 3)
        for side in (-40, 40):
            pygame.draw.circle(surf, (50, 55, 75), (int(x + side), int(y + 20)), 9)
            pygame.draw.circle(surf, ORANGE, (int(x + side), int(y + 20)), 4)
        pulse = 12 + int(math.sin(self.t * 0.15) * 3)
        pygame.draw.circle(surf, (120, 20, 30), (int(x), int(y)), pulse + 4)
        pygame.draw.circle(surf, self.color((255, 70, 70)), (int(x), int(y)), pulse)
        pygame.draw.circle(surf, (255, 200, 200), (int(x - 3), int(y - 3)), pulse // 3)


# ---------------------------------------------------------------- 게임

class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.sfx = SoundBank()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Sky Striker")
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = load_font(46, bold=True)
        self.font = load_font(22, bold=True)
        self.font_small = load_font(16)
        self.tiles = make_tile_surfaces()
        self.cloud_image = make_cloud_image()
        self.high_score = 0
        self.state = "title"
        self.paused = False
        self.reset()

    def reset(self):
        self.bg = Background(self.tiles)
        self.clouds = [Cloud(self.cloud_image) for _ in range(4)]
        self.player = Player()
        self.player_bullets = []
        self.enemy_bullets = []
        self.enemies = []
        self.pending = []      # [남은 프레임, 적] : 편대를 시간차로 등장시키기 위함
        self.particles = []
        self.waves = []
        self.powerups = []
        self.score = 0
        self.lives = 3
        self.stage = 1
        self.stage_timer = 0
        self.wave_timer = 90
        self.boss = None
        self.banner = ("STAGE 1", 150)
        self.flash = 0
        self.shake = 0
        self.dying_timer = 0
        self.hit_sound_cooldown = 0  # 피격음이 한꺼번에 겹쳐 울리지 않게 제한

    # ---- 발사 도우미
    def angle_to_player(self, x, y):
        return math.atan2(self.player.y - y, self.player.x - x)

    def enemy_shot(self, x, y, angle, speed):
        self.enemy_bullets.append(Bullet(x, y, math.cos(angle) * speed, math.sin(angle) * speed, False))

    def shoot_at(self, x, y, speed):
        self.enemy_shot(x, y, self.angle_to_player(x, y), speed)

    # ---- 이펙트
    def explode(self, x, y, count=18, speed=4.0, size=4.0, wave=40):
        for _ in range(count):
            self.particles.append(Particle(x, y, random.choice(FIRE_COLORS), speed,
                                           random.randint(20, 40), size))
        if wave:
            self.waves.append(Shockwave(x, y, wave))

    # ---- 적 생성
    def spawn_wave(self):
        kinds = ["darts", "v", "swoop"]
        weights = [3, 2, 3]
        if self.stage_timer > 8 * FPS or self.stage > 1:
            kinds.append("gunship")
            weights.append(1 + self.stage)
        kind = random.choices(kinds, weights)[0]

        if kind == "darts":
            x = random.uniform(60, WIDTH - 60)
            for i in range(4 + self.stage):
                self.pending.append([i * 14, Dart(x, -20)])
        elif kind == "v":
            cx = random.uniform(120, WIDTH - 120)
            for i in range(5):
                off = (i - 2) * 40
                self.enemies.append(Dart(cx + off, -20 - abs(off)))
        elif kind == "swoop":
            direction = random.choice((1, -1))
            x = -20 if direction == 1 else WIDTH + 20
            y = random.uniform(-10, 120)
            for i in range(5):
                self.pending.append([i * 12, Swooper(x, y, direction)])
        else:
            self.enemies.append(Gunship(random.uniform(80, WIDTH - 80), -40))

    def spawn_turret(self, row):
        candidates = [c for c, kind in enumerate(row) if kind in ("grass", "sand", "road")]
        if candidates and random.random() < 0.07 + 0.02 * self.stage:
            c = random.choice(candidates)
            # 같은 프레임에 update 로 한 번 더 내려가므로 미리 보정
            self.enemies.append(Turret(c * TILE + TILE / 2, self.bg.row_center_y(0) - SCROLL_SPEED))

    # ---- 처리
    def kill_enemy(self, enemy):
        enemy.dead = True
        self.score += enemy.score
        if isinstance(enemy, Boss):
            for _ in range(6):
                self.explode(enemy.x + random.uniform(-60, 60), enemy.y + random.uniform(-40, 40),
                             30, 6.0, 5.0, 90)
            self.shake = 40
            self.flash = 12
            self.sfx.play("big_explode")
            self.sfx.play("stage")
            self.enemy_bullets.clear()
            self.powerups += [PowerUp(enemy.x - 30, enemy.y, "P"), PowerUp(enemy.x + 30, enemy.y, "B")]
            self.boss = None
            self.stage += 1
            self.stage_timer = 0
            self.wave_timer = 180
            self.banner = (f"STAGE {self.stage}", 180)
            return
        big = enemy.radius > 20
        self.explode(enemy.x, enemy.y, 30 if big else 16, 5.0 if big else 3.5, 5.0 if big else 3.5,
                     60 if big else 30)
        if big:
            self.shake = max(self.shake, 8)
        self.sfx.play("big_explode" if big else "explode")
        if random.random() < enemy.drop_chance:
            self.powerups.append(PowerUp(enemy.x, enemy.y, random.choice("PPB")))

    def use_bomb(self):
        if self.player.bombs <= 0 or self.dying_timer:
            return
        self.player.bombs -= 1
        self.player.invuln = max(self.player.invuln, 60)
        self.flash = 20
        self.shake = 20
        self.sfx.play("bomb")
        for b in self.enemy_bullets:
            self.particles.append(Particle(b.x, b.y, (255, 200, 230), 1.5, 15, 2))
        self.enemy_bullets.clear()
        for e in self.enemies:
            if not e.dead and e.y > -20:
                e.hit(30)
                if e.hp <= 0:
                    self.kill_enemy(e)

    def player_hit(self):
        p = self.player
        self.explode(p.x, p.y, 40, 6.0, 5.0, 80)
        self.shake = 25
        self.sfx.play("player_die")
        self.lives -= 1
        p.power = max(1, p.power - 1)
        self.enemy_bullets.clear()
        if self.lives <= 0:
            self.dying_timer = 120
        else:
            p.respawn()

    def update(self, keys):
        new_row = self.bg.update()
        if new_row and not self.boss:
            self.spawn_turret(new_row)
        for c in self.clouds:
            c.update()

        # 적 등장
        self.stage_timer += 1
        if self.boss is None:
            if self.stage_timer >= BOSS_INTERVAL:
                self.boss = Boss(self.stage)
                self.enemies.append(self.boss)
                self.banner = ("WARNING!", 150)
                self.sfx.play("warning")
            else:
                self.wave_timer -= 1
                if self.wave_timer <= 0:
                    self.spawn_wave()
                    self.wave_timer = max(40, 110 - self.stage * 12) + random.randint(0, 40)
        for item in self.pending:
            item[0] -= 1
            if item[0] <= 0:
                self.enemies.append(item[1])
        self.pending = [item for item in self.pending if item[0] > 0]

        # 이동
        alive = not self.dying_timer
        if alive:
            self.player.update(keys, self)
        for group in (self.player_bullets, self.enemy_bullets, self.powerups):
            for obj in group:
                obj.update()
        for e in self.enemies:
            e.update(self)
        for fx in self.particles + self.waves:
            fx.update()

        # 아군 탄 -> 적
        for b in self.player_bullets:
            for e in self.enemies:
                if e.dead or e.y < -10:
                    continue
                if (b.x - e.x) ** 2 + (b.y - e.y) ** 2 < (e.radius + b.radius) ** 2:
                    b.dead = True
                    e.hit(b.damage)
                    self.particles.append(Particle(b.x, b.y, YELLOW, 2.0, 10, 2))
                    if e.hp <= 0:
                        self.kill_enemy(e)
                    elif not self.hit_sound_cooldown:
                        self.sfx.play("hit")
                        self.hit_sound_cooldown = 5
                    break
        if self.hit_sound_cooldown:
            self.hit_sound_cooldown -= 1

        p = self.player
        if alive:
            # 아이템 획득
            for item in self.powerups:
                if (item.x - p.x) ** 2 + (item.y - p.y) ** 2 < 24 ** 2:
                    item.dead = True
                    if item.kind == "P":
                        if p.power < Player.MAX_POWER:
                            p.power += 1
                            self.banner = (f"POWER UP  x{p.shot_count}", 70)
                        else:
                            self.score += 1000
                        self.sfx.play("powerup")
                    else:
                        p.bombs = min(5, p.bombs + 1)
                        self.sfx.play("item")
            # 피격
            if not p.invuln:
                hit = any((b.x - p.x) ** 2 + (b.y - p.y) ** 2 < (b.radius + p.radius) ** 2
                          for b in self.enemy_bullets)
                for e in self.enemies:
                    if not e.dead and not e.ground and \
                            (e.x - p.x) ** 2 + (e.y - p.y) ** 2 < (e.radius * 0.8 + p.radius) ** 2:
                        hit = True
                        if not isinstance(e, Boss):
                            self.kill_enemy(e)
                if hit:
                    self.player_hit()
        else:
            self.dying_timer -= 1
            if self.dying_timer <= 0:
                self.high_score = max(self.high_score, self.score)
                self.state = "gameover"

        # 정리
        self.player_bullets = [b for b in self.player_bullets if not b.dead]
        self.enemy_bullets = [b for b in self.enemy_bullets if not b.dead]
        self.powerups = [i for i in self.powerups if not i.dead]
        self.enemies = [e for e in self.enemies if not e.dead and not e.offscreen()]
        self.particles = [fx for fx in self.particles if fx.life > 0]
        self.waves = [fx for fx in self.waves if fx.life > 0]
        self.high_score = max(self.high_score, self.score)
        if self.flash:
            self.flash -= 1
        if self.shake:
            self.shake -= 1
        if self.banner[1] > 0:
            self.banner = (self.banner[0], self.banner[1] - 1)

    # ---- 그리기
    def draw_world(self, surf):
        self.bg.draw(surf)
        for e in self.enemies:
            if e.ground:
                e.draw(surf)
        for c in self.clouds:
            c.draw(surf)
        for item in self.powerups:
            item.draw(surf, self.font_small)
        for e in self.enemies:
            if not e.ground:
                e.draw(surf)
        if self.state == "playing" and not self.dying_timer:
            self.player.draw(surf)
        for b in self.player_bullets:
            b.draw(surf)
        for fx in self.waves + self.particles:
            fx.draw(surf)
        for b in self.enemy_bullets:
            b.draw(surf)
        if self.flash:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, min(200, self.flash * 12)))
            surf.blit(overlay, (0, 0))

    def draw_hud(self, surf):
        draw_text(surf, self.font, f"SCORE {self.score:,}", WHITE, (12, 10), "topleft")
        draw_text(surf, self.font_small, f"HI {self.high_score:,}", YELLOW, (WIDTH - 12, 14), "topright")

        for i in range(max(0, self.lives - 1)):
            x, y = 20 + i * 24, HEIGHT - 22
            pygame.draw.polygon(surf, (200, 210, 225),
                                [(x, y - 9), (x + 8, y + 6), (x, y + 3), (x - 8, y + 6)])
        for i in range(self.player.bombs):
            x, y = WIDTH - 20 - i * 24, HEIGHT - 22
            pygame.draw.circle(surf, (80, 170, 255), (x, y), 9)
            draw_text(surf, self.font_small, "B", WHITE, (x, y), shadow=False)
        p = self.player
        draw_text(surf, self.font_small,
                  f"POWER {'■' * p.power}{'□' * (Player.MAX_POWER - p.power)}  x{p.shot_count}",
                  ORANGE, (WIDTH / 2, HEIGHT - 22))

        if self.boss and self.boss.y >= 140:
            w = WIDTH - 80
            pygame.draw.rect(surf, (60, 20, 20), (40, 44, w, 8))
            pygame.draw.rect(surf, RED, (40, 44, int(w * self.boss.hp / self.boss.max_hp), 8))
            pygame.draw.rect(surf, WHITE, (40, 44, w, 8), 1)

        text, timer = self.banner
        if timer > 0 and (timer // 8) % 4 != 0:
            draw_text(surf, self.font_big, text, RED if text.startswith("WARN") else WHITE,
                      (WIDTH / 2, HEIGHT / 2 - 60))

    def draw_overlay(self, surf, title, lines):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 20, 150))
        surf.blit(dim, (0, 0))
        draw_text(surf, self.font_big, title, YELLOW, (WIDTH / 2, HEIGHT / 2 - 120))
        for i, line in enumerate(lines):
            draw_text(surf, self.font_small if i else self.font, line, WHITE,
                      (WIDTH / 2, HEIGHT / 2 - 40 + i * 30 + (10 if i else 0)))

    def draw(self):
        surf = self.canvas
        self.draw_world(surf)
        if self.state == "title":
            self.draw_overlay(surf, "SKY STRIKER", [
                "Enter 키를 눌러 시작",
                "방향키 / WASD : 이동",
                "Space / Z : 발사     X : 폭탄",
                "P : 일시정지   M : 소리   Esc : 종료",
                f"HI SCORE {self.high_score:,}",
            ])
        else:
            self.draw_hud(surf)
            if self.state == "gameover":
                self.draw_overlay(surf, "GAME OVER", [
                    f"SCORE {self.score:,}",
                    f"HI SCORE {self.high_score:,}",
                    "Enter 키를 눌러 다시 시작",
                ])
            elif self.paused:
                self.draw_overlay(surf, "PAUSED", ["P 키를 눌러 계속"])

        ox = oy = 0
        if self.shake:
            ox, oy = random.randint(-5, 5), random.randint(-5, 5)
        self.screen.fill(BLACK)
        self.screen.blit(surf, (ox, oy))
        pygame.display.flip()

    # ---- 메인 루프
    def handle_key(self, key):
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        if key == pygame.K_m:
            self.sfx.muted = not self.sfx.muted
        elif self.state in ("title", "gameover") and key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.reset()
            self.state = "playing"
            self.paused = False
            self.sfx.play("stage")
        elif self.state == "playing":
            if key == pygame.K_p:
                self.paused = not self.paused
            elif key == pygame.K_x and not self.paused:
                self.use_bomb()

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)

            if self.state == "playing" and not self.paused:
                self.update(pygame.key.get_pressed())
            elif self.state != "playing":
                # 타이틀/게임오버 화면에서도 배경과 이펙트는 계속 움직임
                self.bg.update()
                for c in self.clouds:
                    c.update()
                for fx in self.particles + self.waves:
                    fx.update()
                self.particles = [fx for fx in self.particles if fx.life > 0]
                self.waves = [fx for fx in self.waves if fx.life > 0]
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
