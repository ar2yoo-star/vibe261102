"""네이버 검색 결과에서 뉴스 기사를 찾아 본문까지 크롤링하는 PyQt6 GUI 앱.

사용법:
    pip install requests beautifulsoup4 PyQt6 openpyxl
    python naver_news_crawler.py

네이버 검색 결과 페이지의 CSS 클래스명은 난독화되어 자주 바뀌므로,
검색 페이지에서는 '네이버뉴스' 링크(n.news.naver.com)만 골라내고
기사 내용은 구조가 안정적인 네이버뉴스 기사 페이지에서 추출한다.
"""

import csv
import html
import os
import sys
import time
from urllib.parse import quote, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

# 통합검색(nexearch)에는 뉴스가 몇 건만 노출되므로 뉴스 탭(where=news)도 함께 사용한다.
SEARCH_URL = "https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={}"
NEWS_TAB_URL = "https://search.naver.com/search.naver?where=news&ie=utf8&query={}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

FIELDS = ["title", "press", "date", "reporter", "url", "content"]
# 엑셀 시트의 열 제목과 열 너비
EXCEL_COLUMNS = [
    ("제목", 50),
    ("언론사", 14),
    ("날짜", 20),
    ("기자", 14),
    ("URL", 45),
    ("본문", 100),
]
EXCEL_CELL_LIMIT = 32767  # 엑셀 셀 하나에 들어갈 수 있는 최대 글자 수


# ---------------------------------------------------------------- 크롤링 로직

def get_soup(url):
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def collect_article_urls(search_url):
    """검색 결과 페이지에서 네이버뉴스 기사 URL을 중복 없이 수집한다."""
    soup = get_soup(search_url)
    urls = []
    for a in soup.select('a[href*="n.news.naver.com/mnews/article"]'):
        # 쿼리스트링(?sid=...)을 제거해 같은 기사가 중복되지 않게 한다
        url = urlunparse(urlparse(a["href"])._replace(query=""))
        if url not in urls:
            urls.append(url)
    return urls


def text_of(soup, selector, attr=None):
    el = soup.select_one(selector)
    if el is None:
        return ""
    return el.get(attr, "") if attr else el.get_text(strip=True)


def parse_article(url):
    """네이버뉴스 기사 페이지에서 제목, 언론사, 날짜, 기자, 본문을 추출한다."""
    soup = get_soup(url)

    body = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    if body:
        # 사진 설명, 스크립트 등 본문이 아닌 요소 제거
        for tag in body.select("script, style, .img_desc, .end_photo_org em"):
            tag.decompose()
        content = body.get_text("\n", strip=True)
    else:
        content = ""

    return {
        "title": text_of(soup, "#title_area") or text_of(soup, "h2.media_end_head_headline"),
        "press": text_of(soup, ".media_end_head_top_logo img", "alt"),
        "date": text_of(soup, "span.media_end_head_info_datestamp_time", "data-date-time"),
        "reporter": text_of(soup, "em.media_end_head_journalist_name"),
        "url": url,
        "content": content,
    }


# ---------------------------------------------------------------- 백그라운드 작업

class CrawlWorker(QThread):
    """네트워크 요청이 UI를 멈추지 않도록 별도 스레드에서 크롤링한다."""

    status = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    article_found = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, keyword, max_count):
        super().__init__()
        self.keyword = keyword
        self.max_count = max_count
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        query = quote(self.keyword)
        try:
            self.status.emit("검색 결과에서 기사 링크를 찾는 중...")
            urls = collect_article_urls(SEARCH_URL.format(query))
            for url in collect_article_urls(NEWS_TAB_URL.format(query)):
                if url not in urls:
                    urls.append(url)
        # 스레드 안의 예외가 처리되지 않으면 PyQt가 앱을 강제 종료하므로 모두 잡아서 알린다
        except Exception as e:
            self.failed.emit(f"검색 페이지를 불러오지 못했습니다.\n{e}")
            return

        urls = urls[: self.max_count]
        if not urls:
            self.status.emit("네이버뉴스 기사를 찾지 못했습니다.")
            return

        for i, url in enumerate(urls, 1):
            if self._stopped:
                self.status.emit(f"중지됨 ({i - 1}/{len(urls)}건 수집)")
                return
            self.status.emit(f"기사 수집 중... ({i}/{len(urls)})")
            try:
                self.article_found.emit(parse_article(url))
            except Exception:
                pass  # 실패한 기사(네트워크 오류, 페이지 구조 변경 등)는 건너뛴다
            self.progress.emit(i, len(urls))
            time.sleep(0.5)  # 서버 부담을 줄이기 위한 요청 간격

        self.status.emit(f"완료: {len(urls)}건 처리")


# ---------------------------------------------------------------- 화면

# 언론사마다 고정된 색을 배정해 목록과 본문에서 구분하기 쉽게 한다
PRESS_COLORS = ["#9fb1d1", "#c9a9a6", "#c8b98f", "#a3c0a8", "#a9bccf", "#b8a9c6", "#97bcbc", "#c4b49a"]

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
QLabel#chip {
    color: #e2e5ea; font-weight: 700; padding: 8px 16px; border-radius: 14px;
    background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
}

QFrame#card { background: #252a34; border: 1px solid #323846; border-radius: 16px; }
QLabel#sectionTitle { color: #b7c0d0; font-size: 15px; font-weight: 700; background: transparent; }
QLabel#fieldLabel { color: #9aa2b1; font-weight: 600; background: transparent; }

QLineEdit, QSpinBox {
    background: #1c2028; border: 2px solid #3a4150; border-radius: 10px;
    padding: 8px 12px; color: #e2e5ea; font-size: 14px;
    selection-background-color: #4a5e80;
}
QLineEdit:focus, QSpinBox:focus { border: 2px solid #7088ad; }
QLineEdit:disabled, QSpinBox:disabled { color: #6b7280; }

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

QTextBrowser { background: #20242d; border: none; border-radius: 10px; padding: 12px; }

QSplitter::handle { background: transparent; height: 10px; }

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


def press_color(name):
    return PRESS_COLORS[sum(map(ord, name)) % len(PRESS_COLORS)]


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
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1200, 820)
        self.setStyleSheet(STYLE)
        self.articles = []
        self.worker = None

        # 헤더: 그라데이션 배너 + 통계 칩
        header = QFrame(objectName="header")
        header.setFixedHeight(96)
        glow = QGraphicsDropShadowEffect(blurRadius=40, xOffset=0, yOffset=8)
        glow.setColor(QColor(0, 0, 0, 110))
        header.setGraphicsEffect(glow)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(QLabel("📰  NEWS CRAWLER", objectName="appTitle"))
        title_box.addWidget(QLabel("네이버 검색 결과에서 뉴스 기사를 한 번에 모아 보세요", objectName="appSubtitle"))
        self.count_chip = QLabel("📄 기사 0건", objectName="chip")
        self.press_chip = QLabel("🏢 언론사 0곳", objectName="chip")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 12, 26, 12)
        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self.count_chip)
        header_layout.addWidget(self.press_chip)

        # 검색 카드: 검색어, 최대 건수, 버튼
        self.keyword_edit = QLineEdit("반도체")
        self.keyword_edit.setPlaceholderText("검색어를 입력하세요")
        self.keyword_edit.returnPressed.connect(self.start_crawl)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 100)
        self.count_spin.setValue(20)
        self.count_spin.setSuffix(" 건")
        # 화살표 버튼 대신 키보드 위/아래 키나 마우스 휠로 값을 바꾼다
        self.count_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.count_spin.setToolTip("마우스 휠이나 ↑↓ 키로 바꿀 수 있습니다")
        self.count_spin.setMinimumWidth(90)
        self.start_btn = QPushButton("🚀 크롤링 시작", objectName="primary")
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

        search_card, search_layout = make_card()
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("🔍 검색어", objectName="fieldLabel"))
        row.addWidget(self.keyword_edit, 1)
        row.addWidget(QLabel("최대", objectName="fieldLabel"))
        row.addWidget(self.count_spin)
        row.addSpacing(6)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addSpacing(6)
        row.addWidget(self.save_btn)
        row.addWidget(self.excel_btn)
        search_layout.addLayout(row)

        # 기사 목록 카드
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["언론사", "날짜", "제목"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.show_article)
        list_card, list_layout = make_card("📋 기사 목록")
        list_layout.addWidget(self.table)

        # 본문 카드
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)
        viewer_card, viewer_layout = make_card("📖 기사 본문")
        viewer_layout.addWidget(self.viewer)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(list_card)
        splitter.addWidget(viewer_card)
        splitter.setSizes([380, 420])

        # 하단: 진행 상태
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.status_label = QLabel("✨ 검색어를 입력하고 '크롤링 시작'을 누르세요.", objectName="status")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 14)
        layout.setSpacing(14)
        layout.addWidget(header)
        layout.addWidget(search_card)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        central = QWidget(objectName="central")
        central.setLayout(layout)
        self.setCentralWidget(central)

    def update_chips(self):
        presses = {a["press"] for a in self.articles if a["press"]}
        self.count_chip.setText(f"📄 기사 {len(self.articles)}건")
        self.press_chip.setText(f"🏢 언론사 {len(presses)}곳")

    def start_crawl(self):
        keyword = self.keyword_edit.text().strip()
        if not keyword:
            QMessageBox.warning(self, "알림", "검색어를 입력하세요.")
            return
        if self.worker and self.worker.isRunning():
            return

        self.articles.clear()
        self.update_chips()
        self.table.setRowCount(0)
        self.viewer.clear()
        self.progress_bar.setValue(0)
        self.set_running(True)

        self.worker = CrawlWorker(keyword, self.count_spin.value())
        self.worker.status.connect(self.status_label.setText)
        self.worker.progress.connect(self.update_progress)
        self.worker.article_found.connect(self.add_article)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(lambda: self.set_running(False))
        self.worker.start()

    def stop_crawl(self):
        if self.worker:
            self.worker.stop()
            self.stop_btn.setEnabled(False)

    def set_running(self, running):
        self.start_btn.setEnabled(not running)
        self.keyword_edit.setEnabled(not running)
        self.count_spin.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.save_btn.setEnabled(not running and bool(self.articles))
        self.excel_btn.setEnabled(not running and bool(self.articles))

    def update_progress(self, done, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)

    def add_article(self, article):
        self.articles.append(article)
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, key in enumerate(["press", "date", "title"]):
            item = QTableWidgetItem(article[key])
            if key == "press":
                item.setForeground(QColor(press_color(article["press"])))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            elif key == "date":
                item.setForeground(QColor("#9aa2b1"))
            self.table.setItem(row, col, item)
        self.update_chips()
        if row == 0:
            self.table.selectRow(0)

    def show_article(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.articles):
            return
        a = {k: html.escape(v) for k, v in self.articles[row].items()}
        paragraphs = "".join(
            f"<p style='line-height:160%; color:#cfd3da; font-size:14px;'>{line}</p>"
            for line in a["content"].split("\n")
        )
        color = press_color(self.articles[row]["press"])
        # setHtml은 이전 기사의 글자 서식(굵게 등)을 남기지 않는다
        self.viewer.setHtml(
            f"<p><span style='background-color:{color}; color:#1c2028; font-weight:700;'>"
            f"&nbsp;{a['press']}&nbsp;</span>"
            f"<span style='color:#9aa2b1;'>&nbsp;&nbsp;🕒 {a['date']}&nbsp;&nbsp;✍ {a['reporter']}</span></p>"
            f"<p style='font-size:21px; font-weight:800; color:#e8eaee;'>{a['title']}</p>"
            f"<p><a href='{a['url']}' style='color:#8fa9cc;'>🔗 원문 보기 — {a['url']}</a></p>"
            f"<hr>{paragraphs}"
        )

    def on_failed(self, message):
        self.status_label.setText("오류 발생")
        QMessageBox.critical(self, "오류", message)

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "naver_news.csv", "CSV 파일 (*.csv)")
        if not path:
            return
        # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않는다
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.articles)
        self.status_label.setText(f"{len(self.articles)}건을 {path} 에 저장했습니다.")

    def save_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", "naver_news.xlsx", "엑셀 파일 (*.xlsx)")
        if not path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "뉴스"
        ws.append([name for name, _ in EXCEL_COLUMNS])
        for article in self.articles:
            # 엑셀이 허용하지 않는 제어문자를 지우고, 셀 글자 수 제한에 맞춘다
            ws.append([ILLEGAL_CHARACTERS_RE.sub("", article[key])[:EXCEL_CELL_LIMIT] for key in FIELDS])

        header_fill = PatternFill("solid", fgColor="DDEBF7")
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        for col, (_, width) in enumerate(EXCEL_COLUMNS, 1):
            ws.column_dimensions[ws.cell(1, col).column_letter].width = width
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=cell.column == 6)
            url_cell = row[4]
            url_cell.hyperlink = url_cell.value
            url_cell.style = "Hyperlink"
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        try:
            wb.save(path)
        except PermissionError:
            QMessageBox.critical(self, "오류", "파일을 저장할 수 없습니다.\n엑셀에서 열려 있다면 닫고 다시 시도하세요.")
            return
        self.status_label.setText(f"{len(self.articles)}건을 {path} 에 저장했습니다.")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()


def resource_path(name):
    """PyInstaller로 묶은 exe에서는 임시 폴더(_MEIPASS)에서 파일을 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 스타일시트가 OS 테마와 섞이지 않게 한다
    app.setFont(QFont("Malgun Gothic", 10))
    app.setWindowIcon(QIcon(resource_path("naver_news_crawler.ico")))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
