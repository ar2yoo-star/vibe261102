"""대한민국 출생아수·합계출산율·자연증가 분석기 (PyQt6 GUI, KOSIS 인구동향조사)

데이터 클랜징 → Pandas 다각도 분석 → 출생아수 라인그래프(기본 1970 ~ 2026)를
탭 형태의 데스크톱 앱으로 보여준다.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QTableView, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

DEFAULT_XLSX = Path(__file__).with_name("출생아수__합계출산율__자연증가_등_2026.xlsx")
DEFAULT_START, DEFAULT_END = 1970, 2026

COLUMN_MAP = {
    "출생아수(명)": "출생아수",
    "자연증가건수(명)": "자연증가건수",
    "조출생률(천명당)": "조출생률",
    "자연증가율(천명당)": "자연증가율",
    "합계출산율(명)": "합계출산율",
    "출생성비(명)": "출생성비",
}
VALUE_COLS = list(COLUMN_MAP.values())

plt.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# 1. 데이터 클랜징
# ---------------------------------------------------------------------------
def load_and_clean(path):
    """엑셀을 읽어 정제한 DataFrame과 클랜징 로그(문자열 리스트)를 돌려준다."""
    log = []
    raw = pd.read_excel(path, sheet_name="데이터", header=None)
    log.append(f"원본 크기: {raw.shape[0]}행(지표) x {raw.shape[1]}열(연도) — 가로형")

    # 첫 열을 지표명 인덱스로, 첫 행을 연도 헤더로 사용한 뒤 전치 → 연도별 행
    raw = raw.set_index(0)
    raw.columns = raw.iloc[0]
    df = raw.iloc[1:].T
    df.columns.name = None
    df = df.rename(columns=lambda c: COLUMN_MAP.get(str(c).strip(), str(c).strip()))
    log.append("행·열 전치 → 연도별 세로형, 지표명 단축 (예: '출생아수(명)' → '출생아수')")

    # 연도 정리: '2025 p)' 같은 잠정치 표기를 분리
    year_str = pd.Series(df.index.astype(str).str.strip(), index=df.index)
    df["잠정치"] = year_str.str.contains("p", case=False)
    df["연도"] = pd.to_numeric(year_str.str.extract(r"(\d{4})")[0], errors="coerce").astype("Int64")

    # 지표 값은 모두 숫자로 변환 (문자/공백 → NaN)
    for col in VALUE_COLS:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce")

    before = len(df)
    df = df.reset_index(drop=True).dropna(subset=["연도"]).drop_duplicates(subset="연도", keep="last")
    df = df.sort_values("연도").set_index("연도")[VALUE_COLS + ["잠정치"]]
    df[["출생아수", "자연증가건수"]] = df[["출생아수", "자연증가건수"]].astype("Int64")
    log.append(f"연도 변환 실패·중복 제거: {before - len(df)}행")

    prelim = df.index[df["잠정치"]].tolist()
    log.append(f"잠정치 연도: {prelim or '없음'} ('YYYY p)' 표기를 연도 + 잠정치 플래그로 분리)")
    log.append("지표별 결측치: " + ", ".join(f"{c}={n}" for c, n in df[VALUE_COLS].isna().sum().items()))
    missing = sorted(set(range(df.index.min(), df.index.max() + 1)) - set(df.index))
    log.append(f"누락 연도: {missing or '없음'}")

    # 추세가 강한 데이터라 '전년 대비 변화율' 기준 IQR로 이상치 점검
    pct = df["출생아수"].astype(float).pct_change() * 100
    q1, q3 = pct.quantile([0.25, 0.75])
    outliers = pct[(pct < q1 - 1.5 * (q3 - q1)) | (pct > q3 + 1.5 * (q3 - q1))]
    log.append("출생아수 전년 대비 변화율 이상치(IQR): "
               + (", ".join(f"{y}년({v:+.1f}%)" for y, v in outliers.items()) or "없음")
               + " (참고용으로 표시만 함)")
    log.append(f"정제 후: {len(df)}행, 기간 {df.index.min()} ~ {df.index.max()}")
    return df, log


# ---------------------------------------------------------------------------
# 2. 다각도 분석
# ---------------------------------------------------------------------------
def analyze(df):
    """분석 결과를 dict로 돌려준다 (요약 텍스트 + 표 DataFrame)."""
    births = df["출생아수"].astype(float)
    tfr = df["합계출산율"]
    values = df[VALUE_COLS].astype(float)
    lines = []

    # 최고·최저 및 장기 변화
    first, last = df.index.min(), df.index.max()
    cagr = (births[last] / births[first]) ** (1 / (last - first)) - 1
    lines += [
        f"출생아수 최고 {births.idxmax()}년 {births.max():,.0f}명, 최저 {births.idxmin()}년 {births.min():,.0f}명",
        f"{first}년 대비 {last}년: {births[last] / births[first]:.1%} 수준 "
        f"({births[last] - births[first]:+,.0f}명), 연평균 증감률(CAGR) {cagr:.2%}",
        f"합계출산율 최고 {tfr.idxmax()}년 {tfr.max():.3f}명, 최저 {tfr.idxmin()}년 {tfr.min():.3f}명",
    ]

    # 연속 감소 구간
    down = (births.diff() < 0).astype(int)
    runs = down.groupby((down != down.shift()).cumsum()).cumsum()
    end = runs.idxmax()
    lines.append(f"최장 연속 감소: {end - runs.max() + 1}~{end}년 ({runs.max()}년 연속)")

    # 최근 반등 여부
    recent = births.pct_change().loc[last - 1:] * 100
    lines.append("최근 2년 출생아수 증감률: "
                 + ", ".join(f"{y}년 {v:+.1f}%" + (" (잠정)" if df.at[y, "잠정치"] else "")
                             for y, v in recent.items()))

    # 출생성비 (자연 상태 정상범위 103~107)
    over = df["출생성비"][df["출생성비"] > 107]
    lines.append(f"출생성비 정상범위(103~107) 초과 {len(over)}개 연도, 최고 {df['출생성비'].idxmax()}년 "
                 f"{df['출생성비'].max():.1f}, 마지막 초과 {over.index.max() if len(over) else '없음'}년")

    # 주요 임계점 도달 시점
    conditions = {
        "출생아수 100만 명 미만": births < 1_000_000,
        "출생아수 50만 명 미만": births < 500_000,
        "출생아수 30만 명 미만": births < 300_000,
        "합계출산율 2.1(대체출산율) 미만": tfr < 2.1,
        "합계출산율 1.3(초저출산) 미만": tfr < 1.3,
        "합계출산율 1.0 미만": tfr < 1.0,
        "자연증가 마이너스(인구 자연감소)": df["자연증가건수"] < 0,
    }
    milestones = pd.DataFrame(
        [(label, f"{mask.fillna(False).idxmax()}년" if mask.any() else "해당 없음")
         for label, mask in conditions.items()],
        columns=["임계점", "첫 해"]).set_index("임계점")

    # 10년 단위(연대별) 요약
    decade = (df.index // 10 * 10).astype(str) + "년대"
    decades = values.groupby(decade).agg(
        출생아수_평균=("출생아수", "mean"),
        출생아수_합계=("출생아수", "sum"),
        합계출산율_평균=("합계출산율", "mean"),
        자연증가건수_평균=("자연증가건수", "mean"),
        출생성비_평균=("출생성비", "mean"),
    )
    decades["출생아수_평균_변화율%"] = decades["출생아수_평균"].pct_change() * 100
    decades.index.name = "연대"

    # 전년 대비 증감
    yoy = pd.DataFrame({
        "출생아수": births,
        "증감(명)": births.diff(),
        "증감률%": births.pct_change() * 100,
        "5년 이동평균": births.rolling(5).mean(),
        "합계출산율": tfr,
        "합계출산율 증감": tfr.diff(),
    })
    yoy.index = yoy.index.astype(str) + df["잠정치"].map({True: " (잠정)", False: ""})
    yoy.index.name = "연도"

    top = pd.concat([
        yoy.nlargest(5, "증감률%")[["출생아수", "증감(명)", "증감률%"]].assign(구분="증가"),
        yoy.nsmallest(5, "증감률%")[["출생아수", "증감(명)", "증감률%"]].assign(구분="감소"),
    ])

    stats = values.describe().T
    stats.index.name = "지표"
    corr = values.corr()
    corr.index.name = "지표"

    return {"summary": lines, "milestones": milestones, "decades": decades, "yoy": yoy,
            "top": top, "stats": stats, "corr": corr}


# ---------------------------------------------------------------------------
# 3. GUI
# ---------------------------------------------------------------------------
class PandasModel(QAbstractTableModel):
    """DataFrame을 QTableView에 표시. color에 준 컬럼(True면 전체)은 숫자 양수/음수를 색으로 구분."""

    def __init__(self, df, color=False, decimals=2):
        super().__init__()
        self._df, self._decimals = df, decimals
        self._color_cols = set(range(len(df.columns))) if color is True else \
            {df.columns.get_loc(c) for c in (color or [])}

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        value = self._df.iat[index.row(), index.column()]
        is_num = pd.api.types.is_number(value) and not isinstance(value, bool)
        if role == Qt.ItemDataRole.DisplayRole:
            if pd.isna(value):
                return ""
            if is_num and abs(value) >= 1000:   # 명 단위 큰 수는 정수로
                return f"{value:,.0f}"
            return f"{value:,.{self._decimals}f}" if isinstance(value, float) else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and is_num:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if (role == Qt.ItemDataRole.ForegroundRole and index.column() in self._color_cols
                and is_num and not pd.isna(value)):
            return QColor("#c0392b") if value < 0 else QColor("#1f7a3a")
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._df.columns[section])
        return str(self._df.index[section])


class ChartTab(QWidget):
    """matplotlib Figure + 확대/이동/저장 툴바."""

    def __init__(self, figsize=(12, 6)):
        super().__init__()
        self.figure = Figure(figsize=figsize, tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)


def make_table():
    view = QTableView()
    view.setAlternatingRowColors(True)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return view


def titled(title, widget):
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(QLabel(f"<b>{title}</b>"))
    layout.addWidget(widget)
    return box


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("대한민국 출생아수 분석기")
        self.resize(1300, 800)
        self.df, self.result = None, None

        # 상단 컨트롤 바
        open_btn = QPushButton("엑셀 열기...")
        open_btn.clicked.connect(self.choose_file)
        self.path_label = QLabel("파일을 열어 주세요")
        self.path_label.setStyleSheet("color: gray;")

        self.start_spin = QSpinBox(minimum=1900, maximum=2100, value=DEFAULT_START, suffix="년")
        self.end_spin = QSpinBox(minimum=1900, maximum=2100, value=DEFAULT_END, suffix="년")
        self.ma_check = QCheckBox("5년 이동평균", checked=True)
        self.label_check = QCheckBox("최고·최저 표시", checked=True)
        for w in (self.start_spin, self.end_spin):
            w.valueChanged.connect(self.draw_births_chart)
        for w in (self.ma_check, self.label_check):
            w.toggled.connect(self.draw_births_chart)
        reset_btn = QPushButton("기간 초기화")
        reset_btn.clicked.connect(self.reset_period)
        export_btn = QPushButton("결과 저장...")
        export_btn.clicked.connect(self.export)

        bar = QHBoxLayout()
        bar.addWidget(open_btn)
        bar.addWidget(self.path_label, 1)
        bar.addWidget(QLabel("기간"))
        bar.addWidget(self.start_spin)
        bar.addWidget(QLabel("~"))
        bar.addWidget(self.end_spin)
        bar.addWidget(reset_btn)
        bar.addSpacing(12)
        bar.addWidget(self.ma_check)
        bar.addWidget(self.label_check)
        bar.addSpacing(12)
        bar.addWidget(export_btn)

        # 탭
        self.tabs = QTabWidget()
        self.births_tab = ChartTab()
        self.indicator_tab = ChartTab()
        self.summary_text = QTextEdit(readOnly=True)
        self.summary_text.setFont(QFont("Malgun Gothic", 10))
        self.tables = {key: make_table() for key in
                       ("milestones", "decades", "yoy", "top", "stats", "corr", "data")}

        summary_page = QWidget()
        sp_layout = QHBoxLayout(summary_page)
        sp_layout.addWidget(self.summary_text, 3)
        sp_layout.addWidget(titled("주요 임계점 도달 시점", self.tables["milestones"]), 2)

        stats_page = QWidget()
        st_layout = QVBoxLayout(stats_page)
        st_layout.addWidget(titled("기술통계", self.tables["stats"]))
        st_layout.addWidget(titled("지표 간 상관관계 (피어슨)", self.tables["corr"]))

        change_page = QWidget()
        ch_layout = QHBoxLayout(change_page)
        ch_layout.addWidget(titled("연도별 전년 대비 증감", self.tables["yoy"]), 3)
        ch_layout.addWidget(titled("증감률 상·하위 5개 연도", self.tables["top"]), 2)

        self.tabs.addTab(self.births_tab, "출생아수 차트")
        self.tabs.addTab(self.indicator_tab, "주요 지표 추이")
        self.tabs.addTab(summary_page, "요약")
        self.tabs.addTab(self.tables["decades"], "연대별")
        self.tabs.addTab(change_page, "전년 대비 증감")
        self.tabs.addTab(stats_page, "통계·상관관계")
        self.tabs.addTab(self.tables["data"], "정제 데이터")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(bar)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        if DEFAULT_XLSX.exists():
            self.load(DEFAULT_XLSX)

    # -- 데이터 로드 -----------------------------------------------------------
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "출생아수 엑셀 선택", str(DEFAULT_XLSX.parent),
                                              "엑셀 파일 (*.xlsx *.xls)")
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
            "<p style='color:gray'>※ 출처: 통계청 KOSIS 「인구동향조사」, p) 잠정치</p>")

        r = self.result
        self.tables["milestones"].setModel(PandasModel(r["milestones"]))
        changes = ["증감(명)", "증감률%", "합계출산율 증감"]
        self.tables["decades"].setModel(PandasModel(r["decades"], color=["자연증가건수_평균", "출생아수_평균_변화율%"]))
        self.tables["yoy"].setModel(PandasModel(r["yoy"].iloc[::-1], color=changes, decimals=3))
        self.tables["top"].setModel(PandasModel(r["top"], color=changes[:2]))
        self.tables["stats"].setModel(PandasModel(r["stats"], decimals=3))
        self.tables["corr"].setModel(PandasModel(r["corr"], decimals=3))
        data = self.df.copy()
        data["잠정치"] = data["잠정치"].map({True: "p)", False: ""})
        self.tables["data"].setModel(PandasModel(data.sort_index(ascending=False),
                                                 color=["자연증가건수", "자연증가율"], decimals=3))

        self.draw_births_chart()
        self.draw_indicator_chart()

    def reset_period(self):
        self.start_spin.setValue(DEFAULT_START)
        self.end_spin.setValue(DEFAULT_END)

    def export(self):
        if self.df is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", str(DEFAULT_XLSX.parent))
        if not folder:
            return
        out = Path(folder)
        self.df.to_csv(out / "출생아수_정제.csv", encoding="utf-8-sig")
        self.result["decades"].to_csv(out / "연대별_요약.csv", encoding="utf-8-sig")
        name = f"출생아수_{self.start_spin.value()}_{self.end_spin.value()}.png"
        self.births_tab.figure.savefig(out / name, dpi=150)
        QMessageBox.information(self, "저장 완료",
                                f"{out}\n\n• 출생아수_정제.csv\n• 연대별_요약.csv\n• {name}")

    # -- 차트 ------------------------------------------------------------------
    def draw_births_chart(self):
        if self.df is None:
            return
        start, end = self.start_spin.value(), self.end_spin.value()
        data = self.df.loc[start:end, ["출생아수", "잠정치"]]
        births = data["출생아수"].astype(float)

        fig = self.births_tab.figure
        fig.clear()
        ax = fig.add_subplot()
        if data.empty or start > end:
            ax.text(0.5, 0.5, "선택한 기간에 데이터가 없습니다", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="gray")
            ax.set_axis_off()
            self.births_tab.canvas.draw_idle()
            return

        confirmed = births[~data["잠정치"]]
        ax.plot(confirmed.index, confirmed, color="#2a6fdb", linewidth=2.2,
                marker="o", markersize=3.5, label="출생아수 (확정)")
        prelim = births[data["잠정치"]]
        if not prelim.empty:   # 잠정치 구간은 점선으로 이어서 표시
            bridge = births.loc[confirmed.index.max() if not confirmed.empty else prelim.index.min():]
            ax.plot(bridge.index, bridge, color="#2a6fdb", linestyle="--", linewidth=2)
            ax.plot(prelim.index, prelim, color="#2a6fdb", linestyle="--", linewidth=2,
                    marker="o", markersize=6, markerfacecolor="white", label="출생아수 (잠정)")

        if self.ma_check.isChecked():   # 이동평균은 기간 밖 데이터까지 써서 계산
            ma = self.df["출생아수"].astype(float).rolling(5).mean().loc[start:end]
            ax.plot(ma.index, ma, color="#999999", linewidth=1.2, linestyle=":", label="5년 이동평균")

        if self.label_check.isChecked():
            # 최고(위), 최저(아래), 마지막 연도(왼쪽 위)로 라벨 위치를 나눠 겹침 방지
            labels = {births.idxmax(): ("최고", (0, 14)), births.idxmin(): ("최저", (0, -30))}
            labels.setdefault(births.index.max(), ("최근", (-10, 22)))
            for year, (tag, offset) in labels.items():
                ax.annotate(f"{tag} {year}년\n{births[year]:,.0f}명", (year, births[year]),
                            textcoords="offset points", xytext=offset, ha="center", fontsize=9,
                            arrowprops=dict(arrowstyle="-", color="gray", lw=0.6))

        ax.set_title(f"대한민국 연도별 출생아수 ({start}~{end})", fontsize=15, fontweight="bold")
        ax.set_xlabel("연도")
        ax.set_ylabel("출생아수 (명)")
        ax.set_xlim(start - 1, end + 1)
        ax.set_ylim(0, births.max() * 1.15)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True, nbins=14))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 10_000:,.0f}만"))
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right")
        ax.text(0.01, 0.02, "출처: 통계청 KOSIS 「인구동향조사」 / p) 잠정치",
                transform=ax.transAxes, fontsize=8, color="gray")
        self.births_tab.canvas.draw_idle()

        msg = f"차트 기간 {births.index.min()} ~ {births.index.max()}년 ({len(births)}개 연도)"
        if end > births.index.max():
            missing = f"{births.index.max() + 1}" + (f"~{end}" if end > births.index.max() + 1 else "")
            msg += f" — {missing}년 데이터는 원본에 없음"
        self.statusBar().showMessage(msg)

    def draw_indicator_chart(self):
        df = self.df
        fig = self.indicator_tab.figure
        fig.clear()
        ax1, ax2, ax3 = fig.subplots(3, 1, sharex=True)

        ax1.plot(df.index, df["합계출산율"], color="#2a6fdb", linewidth=1.8, marker="o", markersize=2.5)
        for level, label in ((2.1, "대체출산율 2.1"), (1.3, "초저출산 1.3"), (1.0, "1.0")):
            ax1.axhline(level, color="gray", linestyle="--", linewidth=0.8)
            ax1.text(df.index.max(), level, f" {label}", va="bottom", ha="right", fontsize=8, color="gray")
        ax1.set_ylabel("합계출산율 (명)")
        ax1.set_title("합계출산율 / 자연증가건수 / 출생성비 추이", fontsize=15)

        natural = df["자연증가건수"].astype(float)
        ax2.bar(df.index, natural, color=["#c0392b" if v < 0 else "#2a9d4b" for v in natural])
        ax2.axhline(0, color="black", linewidth=0.8)
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v / 10_000:,.0f}만"))
        ax2.set_ylabel("자연증가 (명)")

        ax3.plot(df.index, df["출생성비"], color="#e8871e", linewidth=1.8)
        ax3.axhspan(103, 107, color="#2a9d4b", alpha=0.12, label="정상범위 103~107")
        ax3.set_ylabel("출생성비")
        ax3.set_xlabel("연도")
        ax3.legend(loc="upper right", fontsize=8)
        for ax in (ax1, ax2, ax3):
            ax.grid(alpha=0.3)
        self.indicator_tab.canvas.draw_idle()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
