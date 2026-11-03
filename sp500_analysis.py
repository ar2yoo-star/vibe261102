"""S&P 500 과거 데이터 분석기 (PyQt6 GUI)

데이터 클랜징 → Pandas 다각도 분석 → 종가 라인그래프(기본 2000.01 ~ 2019.12)를
탭 형태의 데스크톱 앱으로 보여준다.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDateEdit, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QPushButton, QTableView, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

DEFAULT_CSV = Path(__file__).with_name("S&P 500 과거 데이터.csv")
DEFAULT_START, DEFAULT_END = QDate(2000, 1, 1), QDate(2019, 12, 31)

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# 1. 데이터 클랜징
# ---------------------------------------------------------------------------
def load_and_clean(path):
    """CSV를 읽어 정제한 DataFrame과 클랜징 로그(문자열 리스트)를 돌려준다."""
    log = []
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    log.append(f"원본 크기: {raw.shape[0]:,}행 x {raw.shape[1]}열")
    log.append("컬럼별 결측치: " + ", ".join(f"{c}={n}" for c, n in raw.isna().sum().items()))

    df = raw.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "ChangePct",
    })

    # 날짜: "2019- 11- 14" 처럼 공백이 섞여 있음 → 공백 제거 후 datetime 변환
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", ""), format="%Y-%m-%d", errors="coerce")

    # 가격: "3,096.60" → 천 단위 콤마 제거 후 float
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")

    # 변동률: "-0.20%" → -0.20
    df["ChangePct"] = pd.to_numeric(df["ChangePct"].str.replace("%", ""), errors="coerce")

    # 거래량은 전 구간 비어 있어 분석 의미가 없으므로 제거
    if df["Volume"].isna().all():
        df = df.drop(columns="Volume")
        log.append("'거래량' 컬럼은 100% 결측이라 제거")

    before = len(df)
    df = df.dropna(subset=["Date", "Close"])
    df = df.drop_duplicates(subset="Date", keep="first")
    log.append(f"날짜/종가 변환 실패·중복 제거: {before - len(df)}행")

    # OHLC 논리 검증: 고가 ≥ max(시가, 종가), 저가 ≤ min(시가, 종가)
    bad = df[(df["High"] < df[["Open", "Close"]].max(axis=1)) |
             (df["Low"] > df[["Open", "Close"]].min(axis=1))]
    log.append(f"OHLC 논리 위반 행: {len(bad)}개 (참고용으로 표시만 함)")

    # 최신순 → 과거순 정렬, 날짜를 인덱스로
    df = df.sort_values("Date").set_index("Date")

    # 제공된 변동률과 종가로 직접 계산한 변동률 비교 (데이터 정합성)
    calc = df["Close"].pct_change() * 100
    log.append(f"변동률 불일치(>0.05%p) 행: {((calc - df['ChangePct']).abs() > 0.05).sum()}개")
    log.append(f"정제 후: {len(df):,}행, 기간 {df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}")
    return df, log


# ---------------------------------------------------------------------------
# 2. 다각도 분석
# ---------------------------------------------------------------------------
def analyze(df):
    """분석 결과를 dict로 돌려준다 (요약 텍스트 + 표 DataFrame + 차트용 시리즈)."""
    close = df["Close"]
    ret = close.pct_change()
    lines = []

    # 기간 전체 성과
    years = (close.index[-1] - close.index[0]).days / 365.25
    total = close.iloc[-1] / close.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1
    lines += [
        f"시작 종가 {close.iloc[0]:,.2f} → 마지막 종가 {close.iloc[-1]:,.2f}",
        f"누적 수익률 {total:.2%}, 연평균(CAGR) {cagr:.2%}, 연환산 변동성 {ret.std() * 252 ** 0.5:.2%}",
        f"최고 종가 {close.max():,.2f} ({close.idxmax():%Y-%m-%d}), "
        f"최저 종가 {close.min():,.2f} ({close.idxmin():%Y-%m-%d})",
    ]

    # 연도별 수익률 / 변동성
    yearly = pd.DataFrame({
        "연초종가": close.resample("YE").first(),
        "연말종가": close.resample("YE").last(),
        "연수익률%": close.resample("YE").last().pct_change() * 100,
        "연변동성%": ret.resample("YE").std() * 252 ** 0.5 * 100,
        "거래일수": close.resample("YE").count(),
    })
    # 첫 해는 전년 말 데이터가 없으므로 연초 종가 기준
    yearly.iloc[0, 2] = (yearly.iloc[0, 1] / yearly.iloc[0, 0] - 1) * 100
    yearly.index = yearly.index.year.astype(str)
    yearly.index.name = "연도"
    lines.append(f"최고의 해 {yearly['연수익률%'].idxmax()} ({yearly['연수익률%'].max():.2f}%), "
                 f"최악의 해 {yearly['연수익률%'].idxmin()} ({yearly['연수익률%'].min():.2f}%)")

    # 월별 수익률 (연 x 월 피벗)
    monthly = close.resample("ME").last().pct_change() * 100
    pivot = monthly.to_frame("ret").assign(Y=monthly.index.year, M=monthly.index.month) \
        .pivot(index="Y", columns="M", values="ret")
    pivot.loc["평균"] = pivot.mean()
    pivot.loc["상승확률%"] = (pivot.iloc[:-1] > 0).mean() * 100
    pivot.index = pivot.index.astype(str)
    pivot.columns = [f"{m}월" for m in pivot.columns]

    # 요일별 일간 수익률 패턴
    dow = (ret * 100).groupby(ret.index.dayofweek).agg(["mean", "std", "count"])
    dow.index = ["월", "화", "수", "목", "금"][: len(dow)]
    dow.columns = ["평균수익률%", "표준편차%", "거래일수"]
    dow.index.name = "요일"

    # 최대 낙폭 (MDD)
    dd = close / close.cummax() - 1
    trough = dd.idxmin()
    peak_date = close[:trough].idxmax()
    recovered = close[trough:][close[trough:] >= close[peak_date]]
    lines.append(f"MDD {dd.min():.2%}: 고점 {peak_date:%Y-%m-%d} ({close[peak_date]:,.2f}) → "
                 f"저점 {trough:%Y-%m-%d} ({close[trough]:,.2f}), 회복 "
                 + (f"{recovered.index[0]:%Y-%m-%d}" if len(recovered) else "미회복"))
    lines.append(f"일간 ±3% 이상 변동일 수: {(df['ChangePct'].abs() >= 3).sum()}일")

    # 일간 변동 Top 5
    top = pd.concat([
        df["ChangePct"].nlargest(5).rename("변동%").to_frame().assign(구분="상승"),
        df["ChangePct"].nsmallest(5).rename("변동%").to_frame().assign(구분="하락"),
    ])
    top.index = top.index.strftime("%Y-%m-%d")
    top.index.name = "날짜"

    # 이동평균 골든/데드크로스 (50일 vs 200일)
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    signal = (ma50 > ma200).astype(int).diff()
    crosses = signal[(signal != 0) & ma200.notna()].dropna()
    lines.append(f"50/200일 이동평균: 골든크로스 {(crosses == 1).sum()}회, 데드크로스 {(crosses == -1).sum()}회")
    crosses = crosses.map({1: "골든크로스", -1: "데드크로스"}).rename("신호").to_frame()
    crosses.index = crosses.index.strftime("%Y-%m-%d")
    crosses.index.name = "날짜"

    return {"summary": lines, "yearly": yearly, "monthly": pivot, "dow": dow, "top": top,
            "crosses": crosses, "ma50": ma50, "ma200": ma200, "dd": dd}


# ---------------------------------------------------------------------------
# 3. GUI
# ---------------------------------------------------------------------------
class PandasModel(QAbstractTableModel):
    """DataFrame을 QTableView에 표시. color=True면 숫자 양수/음수를 색으로 구분."""

    def __init__(self, df, color=False):
        super().__init__()
        self._df, self._color = df, color

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        value = self._df.iat[index.row(), index.column()]
        is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
        if role == Qt.ItemDataRole.DisplayRole:
            if pd.isna(value):
                return ""
            return f"{value:,.2f}" if isinstance(value, float) else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and is_num:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and self._color and is_num and not pd.isna(value):
            return QColor("#c0392b") if value < 0 else QColor("#1f7a3a")
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        label = self._df.index[section]
        return label.strftime("%Y-%m-%d") if isinstance(label, pd.Timestamp) else str(label)


class ChartTab(QWidget):
    """matplotlib Figure + 확대/이동/저장 툴바."""

    def __init__(self, figsize=(12, 6)):
        super().__init__()
        self.figure = Figure(figsize=figsize, tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S&P 500 과거 데이터 분석기")
        self.resize(1300, 800)
        self.df, self.result = None, None

        # 상단 컨트롤 바
        open_btn = QPushButton("CSV 열기...")
        open_btn.clicked.connect(self.choose_file)
        self.path_label = QLabel("파일을 열어 주세요")
        self.path_label.setStyleSheet("color: gray;")

        self.start_edit = QDateEdit(DEFAULT_START, calendarPopup=True, displayFormat="yyyy-MM-dd")
        self.end_edit = QDateEdit(DEFAULT_END, calendarPopup=True, displayFormat="yyyy-MM-dd")
        self.ma50_check = QCheckBox("50일 이동평균")
        self.ma200_check = QCheckBox("200일 이동평균")
        for w in (self.start_edit, self.end_edit):
            w.dateChanged.connect(self.draw_close_chart)
        for w in (self.ma50_check, self.ma200_check):
            w.toggled.connect(self.draw_close_chart)
        reset_btn = QPushButton("기간 초기화")
        reset_btn.clicked.connect(self.reset_period)

        bar = QHBoxLayout()
        bar.addWidget(open_btn)
        bar.addWidget(self.path_label, 1)
        bar.addWidget(QLabel("기간"))
        bar.addWidget(self.start_edit)
        bar.addWidget(QLabel("~"))
        bar.addWidget(self.end_edit)
        bar.addWidget(reset_btn)
        bar.addSpacing(12)
        bar.addWidget(self.ma50_check)
        bar.addWidget(self.ma200_check)

        # 탭
        self.tabs = QTabWidget()
        self.close_tab = ChartTab()
        self.ma_tab = ChartTab()
        self.summary_text = QTextEdit(readOnly=True)
        self.summary_text.setFont(QFont("Malgun Gothic", 10))
        self.tables = {key: QTableView() for key in ("yearly", "monthly", "dow", "top", "crosses", "data")}
        for view in self.tables.values():
            view.setAlternatingRowColors(True)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        events = QWidget()
        ev_layout = QHBoxLayout(events)
        for title, key in (("일간 변동 Top 5", "top"), ("골든/데드크로스 (50 vs 200일)", "crosses")):
            box = QVBoxLayout()
            box.addWidget(QLabel(f"<b>{title}</b>"))
            box.addWidget(self.tables[key])
            ev_layout.addLayout(box)

        self.tabs.addTab(self.close_tab, "종가 차트")
        self.tabs.addTab(self.ma_tab, "이동평균·낙폭")
        self.tabs.addTab(self.summary_text, "요약")
        self.tabs.addTab(self.tables["yearly"], "연도별")
        self.tabs.addTab(self.tables["monthly"], "월별 수익률")
        self.tabs.addTab(self.tables["dow"], "요일별")
        self.tabs.addTab(events, "주요 이벤트")
        self.tabs.addTab(self.tables["data"], "정제 데이터")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(bar)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        if DEFAULT_CSV.exists():
            self.load(DEFAULT_CSV)

    # -- 데이터 로드 -----------------------------------------------------------
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "S&P 500 CSV 선택", str(DEFAULT_CSV.parent),
                                              "CSV 파일 (*.csv)")
        if path:
            self.load(Path(path))

    def load(self, path):
        try:
            self.df, log = load_and_clean(path)
            self.result = analyze(self.df)
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"{path.name}\n\n{e}")
            return
        self.path_label.setText(str(path))
        self.statusBar().showMessage(log[-1])

        self.summary_text.setHtml(
            "<h3>1. 데이터 클랜징</h3><ul>" + "".join(f"<li>{s}</li>" for s in log) + "</ul>"
            "<h3>2. 분석 요약</h3><ul>" + "".join(f"<li>{s}</li>" for s in self.result["summary"]) + "</ul>"
            "<p style='color:gray'>※ 수익률은 배당을 제외한 지수 기준입니다.</p>")

        self.tables["yearly"].setModel(PandasModel(self.result["yearly"], color=True))
        self.tables["monthly"].setModel(PandasModel(self.result["monthly"], color=True))
        self.tables["dow"].setModel(PandasModel(self.result["dow"], color=True))
        self.tables["top"].setModel(PandasModel(self.result["top"], color=True))
        self.tables["crosses"].setModel(PandasModel(self.result["crosses"]))
        self.tables["data"].setModel(PandasModel(self.df.sort_index(ascending=False), color=False))

        self.draw_close_chart()
        self.draw_ma_chart()

    def reset_period(self):
        self.start_edit.setDate(DEFAULT_START)
        self.end_edit.setDate(DEFAULT_END)

    # -- 차트 ------------------------------------------------------------------
    def draw_close_chart(self):
        if self.df is None:
            return
        start = self.start_edit.date().toString("yyyy-MM-dd")
        end = self.end_edit.date().toString("yyyy-MM-dd")
        period = self.df.loc[start:end, "Close"]

        fig = self.close_tab.figure
        fig.clear()
        ax = fig.add_subplot()
        if period.empty:
            ax.text(0.5, 0.5, "선택한 기간에 데이터가 없습니다", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="gray")
            ax.set_axis_off()
            self.close_tab.canvas.draw_idle()
            return

        ax.plot(period.index, period.values, color="#1f5fa8", linewidth=1.2, label="S&P 500 종가")
        if self.ma50_check.isChecked():
            ax.plot(self.result["ma50"].loc[start:end], color="#e8871e", linewidth=1, label="50일 이동평균")
        if self.ma200_check.isChecked():
            ax.plot(self.result["ma200"].loc[start:end], color="#2a9d4b", linewidth=1, label="200일 이동평균")

        ax.set_title(f"S&P 500 종가 추이 ({period.index.min():%Y.%m} ~ {period.index.max():%Y.%m})",
                     fontsize=15)
        ax.set_xlabel("날짜")
        ax.set_ylabel("종가 (포인트)")
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.grid(alpha=0.3)

        # 구간 내 최고/최저 종가 표시 (점이 오른쪽 절반이면 글자를 왼쪽에, 아니면 오른쪽에)
        mid = period.index[0] + (period.index[-1] - period.index[0]) / 2
        for label, date in [("최고", period.idxmax()), ("최저", period.idxmin())]:
            dx = -70 if date > mid else 70
            ax.annotate(f"{label} {period[date]:,.0f}\n({date:%Y-%m-%d})", xy=(date, period[date]),
                        xytext=(dx, -15 if label == "최고" else 15), textcoords="offset points",
                        ha="center", va="center", fontsize=9,
                        arrowprops=dict(arrowstyle="->", color="gray"))
        ax.legend(loc="best")
        self.close_tab.canvas.draw_idle()
        self.statusBar().showMessage(f"차트 기간 {period.index.min():%Y-%m-%d} ~ "
                                     f"{period.index.max():%Y-%m-%d} ({len(period):,}거래일)")

    def draw_ma_chart(self):
        close, dd = self.df["Close"], self.result["dd"]
        fig = self.ma_tab.figure
        fig.clear()
        ax1, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        ax1.plot(close, color="#1f5fa8", linewidth=1, label="종가")
        ax1.plot(self.result["ma50"], color="#e8871e", linewidth=1, label="50일 이동평균")
        ax1.plot(self.result["ma200"], color="#2a9d4b", linewidth=1, label="200일 이동평균")
        ax1.set_title("S&P 500 종가와 이동평균 / 고점 대비 낙폭", fontsize=15)
        ax1.set_ylabel("종가")
        ax1.legend(loc="upper left")
        ax1.grid(alpha=0.3)

        ax2.fill_between(dd.index, dd * 100, 0, color="#c0392b", alpha=0.4)
        ax2.set_ylabel("낙폭 (%)")
        ax2.grid(alpha=0.3)
        ax2.xaxis.set_major_locator(mdates.YearLocator(2))
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        self.ma_tab.canvas.draw_idle()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
