"""네이버 증권에서 코스피200 구성종목, 코스피·코스닥 종목 중 등락률 상위 종목 시세를 크롤링하는 PyQt6 GUI 앱.

사용법:
    pip install requests PyQt6 openpyxl
    python index_crawler.py

stock.naver.com/domestic/index/KOSPI/price 페이지는 Next.js로 만든 SPA라서
HTML 원문에는 시세 숫자가 없고, 브라우저가 JS로 아래 JSON API를 호출해 화면을 그린다.
그래서 BeautifulSoup로 HTML을 파싱하면 값을 얻을 수 없고, 같은 API를 직접 호출한다.
"""

import csv
import sys
import time

import requests
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

API_URL = "https://m.stock.naver.com/api/index/{code}/{kind}"
# 네이버 증권 지수 코드: 화면에 보일 이름
INDEXES = {
    "KPI200": "코스피 200",
    "KOSPI": "코스피",
    "KOSDAQ": "코스닥",
}
# 지수별 종목 목록 API와 페이지 크기.
# 코스피200은 구성종목 API(최대 60건씩), 코스피·코스닥은 시장 전체 종목 API(최대 100건씩)를 쓴다.
# 네이버의 상승률 순위 API(/stocks/up)는 오른 종목만 돌려줘서 하락장에서는 200개가 안 될 수 있으므로,
# 전체 종목을 받은 뒤 등락률로 직접 정렬한다.
STOCK_SOURCES = {
    "KPI200": ("https://m.stock.naver.com/api/index/KPI200/enrollStocks", 60),
    "KOSPI": ("https://m.stock.naver.com/api/stocks/marketValue/KOSPI", 100),
    "KOSDAQ": ("https://m.stock.naver.com/api/stocks/marketValue/KOSDAQ", 100),
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": "https://stock.naver.com/",
}

# (CSV/엑셀 열 이름, 행 딕셔너리 키, 엑셀 열 너비)
COLUMNS = [
    ("순위", "rank", 7),
    ("종목코드", "code", 10),
    ("종목명", "name", 22),
    ("현재가", "price", 12),
    ("전일대비", "change", 11),
    ("등락률(%)", "rate", 10),
    ("거래량", "volume", 14),
    ("거래대금(백만원)", "value", 16),
    ("시가총액(억원)", "cap", 15),
]
TEXT_KEYS = ("code", "name")  # 엑셀에 숫자로 바꾸지 않고 글자 그대로 넣을 열


# ---------------------------------------------------------------- 크롤링


def get_json(url, params=None):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.json()


def fetch_current(code):
    """현재가(장중이면 실시간, 장 마감 후면 종가)."""
    d = get_json(API_URL.format(code=code, kind="basic"))
    return {
        "name": d.get("stockName", INDEXES[code]),
        "price": d.get("closePrice", ""),
        "change": d.get("compareToPreviousClosePrice", ""),
        "rate": d.get("fluctuationsRatio", ""),
        "status": d.get("marketStatus", ""),
        "time": d.get("localTradedAt", ""),
    }


def fetch_stock_page(code, page):
    """종목 목록 한 페이지. 코스피 목록에 섞여 있는 ETF 등은 빼고 일반 종목만 돌려준다.

    (일반 종목 목록, 필터링 전 API가 돌려준 건수, 시장 전체 종목 수 또는 None)을 돌려준다.
    """
    url, page_size = STOCK_SOURCES[code]
    data = get_json(url, {"page": page, "pageSize": page_size})
    stocks = data["stocks"] if isinstance(data, dict) else data
    return [
        {
            "code": d["itemCode"],
            "name": d["stockName"],
            "price": d["closePrice"],
            "change": d["compareToPreviousClosePrice"],
            "rate": d["fluctuationsRatio"],
            "volume": d["accumulatedTradingVolume"],
            "value": d["accumulatedTradingValue"],
            "cap": d["marketValue"],
        }
        for d in stocks
        if d.get("stockEndType") == "stock"
    ], len(stocks), data.get("totalCount") if isinstance(data, dict) else None


def to_number(text):
    return float(text.replace(",", ""))


def excel_number(text):
    """엑셀 셀에 넣을 숫자. 거래가 없어 '-'처럼 숫자가 아닌 값은 그대로 둔다."""
    try:
        return to_number(text)
    except ValueError:
        return text


def rate_key(stock):
    """정렬용 등락률. 거래정지 등으로 값이 없으면 맨 뒤로 보낸다."""
    try:
        return to_number(stock["rate"])
    except ValueError:
        return float("-inf")


class CrawlWorker(QThread):
    """네트워크 요청이 UI를 멈추지 않도록 별도 스레드에서 크롤링한다."""

    status = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    current_found = pyqtSignal(dict)
    rows_found = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, code, count):
        super().__init__()
        self.code = code
        self.count = count
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        stocks = {}  # 종목코드: 종목. 페이지가 겹쳐 같은 종목이 다시 나와도 한 번만 담는다
        # 스레드 안의 예외가 처리되지 않으면 PyQt가 앱을 강제 종료하므로 모두 잡아서 알린다
        try:
            self.status.emit("지수 현재가를 불러오는 중...")
            self.current_found.emit(fetch_current(self.code))

            # 등락률 순위를 매기려면 전체 종목이 필요하므로 마지막 페이지까지 받는다
            _, page_size = STOCK_SOURCES[self.code]
            total_pages = None
            page = 1
            while total_pages is None or page <= total_pages:
                if self._stopped:
                    self.status.emit(f"중지됨 ({len(stocks)}종목까지 받음)")
                    return
                pages_text = f"{page}/{total_pages}" if total_pages else f"{page}"
                self.status.emit(f"전체 종목 받는 중... ({pages_text}페이지, {len(stocks)}종목)")
                page_stocks, raw_count, total_count = fetch_stock_page(self.code, page)
                if raw_count == 0:
                    break  # 더 이상 종목이 없음
                if total_count:
                    total_pages = -(-total_count // page_size)  # 올림 나눗셈
                for stock in page_stocks:
                    stocks.setdefault(stock["code"], stock)
                if total_pages:
                    self.progress.emit(page, total_pages)
                page += 1
                time.sleep(0.2)  # 서버 부담을 줄이기 위한 요청 간격
        except Exception as e:
            self.failed.emit(f"시세를 불러오지 못했습니다.\n{e}")
            return

        # 등락률이 같으면 원래 순서(시가총액 순)를 유지한다
        ranked = sorted(stocks.values(), key=rate_key, reverse=True)[: self.count]
        for i, stock in enumerate(ranked, 1):
            stock["rank"] = str(i)
        self.rows_found.emit(ranked)
        self.progress.emit(1, 1)
        self.status.emit(f"완료: 전체 {len(stocks)}종목 중 등락률 상위 {len(ranked)}종목")


# ---------------------------------------------------------------- 화면

# 국내 증시 관례: 상승은 빨강, 하락은 파랑
UP_COLOR = "#e07a7a"
DOWN_COLOR = "#7aa2e0"
FLAT_COLOR = "#b7c0d0"

STYLE = """
QMainWindow, QWidget#central { background: #1c2028; }
QWidget { color: #d4d7dd; font-size: 13px; }

QFrame#header {
    border-radius: 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #3a4660, stop:1 #4a5468);
}
QLabel#appTitle { color: #eef0f4; font-size: 26px; font-weight: 800; background: transparent; }
QLabel#appSubtitle { color: #b4bccb; font-size: 13px; background: transparent; }
QLabel#price { font-size: 30px; font-weight: 800; background: transparent; }
QLabel#priceChange { font-size: 15px; font-weight: 700; background: transparent; }
QLabel#priceTime { color: #b4bccb; font-size: 12px; background: transparent; }

QFrame#card { background: #252a34; border: 1px solid #323846; border-radius: 16px; }
QLabel#sectionTitle { color: #b7c0d0; font-size: 15px; font-weight: 700; background: transparent; }
QLabel#fieldLabel { color: #9aa2b1; font-weight: 600; background: transparent; }

QSpinBox, QComboBox {
    background: #1c2028; border: 2px solid #3a4150; border-radius: 10px;
    padding: 8px 12px; color: #e2e5ea; font-size: 14px;
    selection-background-color: #4a5e80;
}
QSpinBox:focus, QComboBox:focus { border: 2px solid #7088ad; }
QSpinBox:disabled, QComboBox:disabled { color: #6b7280; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: #252a34; border: 1px solid #3a4150; color: #e2e5ea;
    selection-background-color: #3d4a63; outline: none; padding: 4px;
}

QPushButton {
    border: none; border-radius: 10px; padding: 10px 18px;
    color: #eef0f4; font-weight: 700; font-size: 13px;
}
QPushButton:disabled { background: #2c313b; color: #5d6470; }
QPushButton#primary { background: #4f6489; }
QPushButton#primary:hover { background: #5c7299; }
QPushButton#danger { background: #8a5656; }
QPushButton#danger:hover { background: #9a6464; }
QPushButton#csv { background: #4a7373; }
QPushButton#csv:hover { background: #568282; }
QPushButton#excel { background: #52725a; }
QPushButton#excel:hover { background: #5e8167; }
QPushButton#primary:disabled, QPushButton#danger:disabled,
QPushButton#csv:disabled, QPushButton#excel:disabled { background: #2c313b; color: #5d6470; }

QTableWidget {
    background: #20242d; alternate-background-color: #242934;
    border: none; border-radius: 10px; gridline-color: transparent;
    selection-background-color: #3d4a63; selection-color: #eef0f4;
}
QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #2c313b; }
QTableWidget::item:selected { background: #3d4a63; color: #eef0f4; }
QHeaderView::section {
    background: #2a303b; color: #b7c0d0; font-weight: 700;
    padding: 8px; border: none; border-bottom: 1px solid #3f4757;
}

QProgressBar {
    background: #2a303b; border: none; border-radius: 7px; height: 14px;
    text-align: center; color: #d4d7dd; font-size: 11px; font-weight: 700;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: #5f7aa0;
}
QLabel#status { color: #9aa2b1; background: transparent; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #3f4757; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #56607a; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


def change_color(change):
    try:
        value = to_number(change)
    except ValueError:
        return FLAT_COLOR
    return UP_COLOR if value > 0 else DOWN_COLOR if value < 0 else FLAT_COLOR


def make_card(title=None):
    """둥근 모서리와 그림자가 있는 카드 패널을 만든다."""
    card = QFrame(objectName="card")
    shadow = QGraphicsDropShadowEffect(blurRadius=30, xOffset=0, yOffset=6)
    shadow.setColor(QColor(0, 0, 0, 160))
    card.setGraphicsEffect(shadow)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)
    if title:
        layout.addWidget(QLabel(title, objectName="sectionTitle"))
    return card, layout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("종목 시세 크롤러")
        self.resize(1150, 800)
        self.setStyleSheet(STYLE)
        self.rows = []
        self.rows_code = None  # self.rows가 어느 지수(시장)의 종목인지
        self.worker = None

        # 헤더: 그라데이션 배너 + 현재가
        header = QFrame(objectName="header")
        header.setFixedHeight(110)
        glow = QGraphicsDropShadowEffect(blurRadius=40, xOffset=0, yOffset=8)
        glow.setColor(QColor(0, 0, 0, 110))
        header.setGraphicsEffect(glow)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel(objectName="appTitle")
        self.subtitle_label = QLabel(objectName="appSubtitle")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        self.price_label = QLabel("-", objectName="price")
        self.change_label = QLabel("", objectName="priceChange")
        self.time_label = QLabel("", objectName="priceTime")
        price_box = QVBoxLayout()
        price_box.setSpacing(0)
        price_box.addWidget(self.price_label, alignment=Qt.AlignmentFlag.AlignRight)
        price_box.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignRight)
        price_box.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignRight)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 12, 26, 12)
        header_layout.addLayout(title_box, 1)
        header_layout.addLayout(price_box)

        # 조작 카드: 지수 선택, 수집 건수, 버튼
        self.index_combo = QComboBox()
        for code, name in INDEXES.items():
            self.index_combo.addItem(name, code)
        self.index_combo.setMinimumWidth(150)
        self.index_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.index_combo.currentIndexChanged.connect(self.on_index_changed)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1000)
        self.count_spin.setSingleStep(50)
        self.count_spin.setValue(200)
        self.count_spin.setSuffix(" 종목")
        # 화살표 버튼 대신 키보드 위/아래 키나 마우스 휠로 값을 바꾼다
        self.count_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.count_spin.setToolTip("마우스 휠이나 ↑↓ 키로 50씩 바꿀 수 있습니다")
        self.count_spin.setMinimumWidth(120)
        self.start_btn = QPushButton("🚀 수집 시작", objectName="primary")
        self.start_btn.clicked.connect(self.start_crawl)
        self.stop_btn = QPushButton("⏹ 중지", objectName="danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.save_btn = QPushButton("💾 CSV 저장", objectName="csv")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_csv)
        self.excel_btn = QPushButton("📊 엑셀 저장", objectName="excel")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel)
        for btn in (self.start_btn, self.stop_btn, self.save_btn, self.excel_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        control_card, control_layout = make_card()
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("📊 지수", objectName="fieldLabel"))
        row.addWidget(self.index_combo)
        row.addSpacing(6)
        row.addWidget(QLabel("🔢 개수", objectName="fieldLabel"))
        row.addWidget(self.count_spin)
        row.addStretch(1)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addSpacing(6)
        row.addWidget(self.save_btn)
        row.addWidget(self.excel_btn)
        control_layout.addLayout(row)

        # 일별 시세 카드
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([name for name, _, _ in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_title = QLabel("📋 등락률 상위", objectName="sectionTitle")
        table_card, table_layout = make_card()
        table_layout.addWidget(self.table_title)
        table_layout.addWidget(self.table)

        # 하단: 진행 상태
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel("✨ 지수와 종목 수를 정하고 '수집 시작'을 누르세요.", objectName="status")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 14)
        layout.setSpacing(14)
        layout.addWidget(header)
        layout.addWidget(control_card)
        layout.addWidget(table_card, 1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        central = QWidget(objectName="central")
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.on_index_changed()

    def selected_code(self):
        return self.index_combo.currentData()

    def on_index_changed(self):
        name = INDEXES[self.selected_code()]
        self.title_label.setText(f"📈  {name}")
        target = "코스피 200 구성종목" if self.selected_code() == "KPI200" else f"{name} 종목"
        self.subtitle_label.setText(f"네이버 증권에서 {target} 중 등락률 상위 종목을 모아 보세요")
        # 다른 지수의 현재가가 남아 있지 않도록 헤더를 비운다
        self.price_label.setText("-")
        self.price_label.setStyleSheet("")
        self.change_label.setText("")
        self.time_label.setText("")

    def start_crawl(self):
        if self.worker and self.worker.isRunning():
            return

        self.rows.clear()
        self.rows_code = self.selected_code()
        self.table.setRowCount(0)
        self.table_title.setText("📋 등락률 상위")
        self.progress_bar.setValue(0)
        self.set_running(True)

        self.worker = CrawlWorker(self.rows_code, self.count_spin.value())
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress.connect(self.update_progress)
        self.worker.current_found.connect(self.show_current)
        self.worker.rows_found.connect(self.add_rows)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.stop()
            self.stop_btn.setEnabled(False)

    def set_running(self, running):
        self.start_btn.setEnabled(not running)
        self.index_combo.setEnabled(not running)
        self.count_spin.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.save_btn.setEnabled(not running and bool(self.rows))
        self.excel_btn.setEnabled(not running and bool(self.rows))

    def update_progress(self, done, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)

    def show_current(self, cur):
        color = change_color(cur["change"])
        arrow = "▲" if color == UP_COLOR else "▼" if color == DOWN_COLOR else ""
        self.price_label.setText(cur["price"])
        self.price_label.setStyleSheet(f"color: {color};")
        self.change_label.setText(f"{arrow} {cur['change'].lstrip('-')}  ({cur['rate']}%)")
        self.change_label.setStyleSheet(f"color: {color};")
        market = "장중" if cur["status"] == "OPEN" else "장마감"
        self.time_label.setText(f"{market} · {cur['time'][:16].replace('T', ' ')}")

    def add_rows(self, rows):
        for r in rows:
            self.rows.append(r)
            row = self.table.rowCount()
            self.table.insertRow(row)
            color = QColor(change_color(r["change"]))
            for col, (_, key, _) in enumerate(COLUMNS):
                item = QTableWidgetItem(r[key])
                if key in ("rank", "code"):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setForeground(QColor("#9aa2b1"))
                elif key == "name":
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if key in ("price", "change", "rate"):
                    item.setForeground(color)
                self.table.setItem(row, col, item)
        self.table_title.setText(f"📋 {INDEXES[self.rows_code]} 등락률 상위  ·  {len(self.rows)}종목")

    def on_failed(self, message):
        self.status_label.setText("오류 발생")
        QMessageBox.critical(self, "오류", message)

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", f"{self.rows_code.lower()}_stocks.csv", "CSV 파일 (*.csv)")
        if not path:
            return
        try:
            # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않는다
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([name for name, _, _ in COLUMNS])
                for r in self.rows:
                    writer.writerow([r[key] for _, key, _ in COLUMNS])
        except PermissionError:
            QMessageBox.critical(self, "오류", "파일을 저장할 수 없습니다.\n엑셀에서 열려 있다면 닫고 다시 시도하세요.")
            return
        self.status_label.setText(f"{len(self.rows)}건을 {path} 에 저장했습니다.")

    def save_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", f"{self.rows_code.lower()}_stocks.xlsx", "엑셀 파일 (*.xlsx)")
        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = INDEXES[self.rows_code]
        ws.append([name for name, _, _ in COLUMNS])
        for r in self.rows:
            # 종목코드·종목명을 뺀 값은 숫자로 넣어 엑셀에서 바로 계산·정렬할 수 있게 한다
            # (종목코드를 숫자로 바꾸면 앞자리 0이 사라진다)
            ws.append([r[key] if key in TEXT_KEYS else excel_number(r[key]) for _, key, _ in COLUMNS])

        header_fill = PatternFill("solid", fgColor="DDEBF7")
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for col, (_, _, width) in enumerate(COLUMNS, 1):
            ws.column_dimensions[ws.cell(1, col).column_letter].width = width
        for row in ws.iter_rows(min_row=2):
            for cell, (_, key, _) in zip(row, COLUMNS):
                if key == "rate":
                    cell.number_format = "0.00"
                elif key not in TEXT_KEYS:
                    cell.number_format = "#,##0"
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        try:
            wb.save(path)
        except PermissionError:
            QMessageBox.critical(self, "오류", "파일을 저장할 수 없습니다.\n엑셀에서 열려 있다면 닫고 다시 시도하세요.")
            return
        self.status_label.setText(f"{len(self.rows)}건을 {path} 에 저장했습니다.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 스타일시트가 OS 테마와 섞이지 않게 한다
    app.setFont(QFont("Malgun Gothic", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
