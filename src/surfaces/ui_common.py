"""Reusable controls and centralized light interface tokens."""

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

STYLE = """
QMainWindow, QDialog { background: #f3f5f8; }
QWidget { color: #243247; font-size: 13px; }
QToolBar { background: #ffffff; border-bottom: 1px solid #dce2eb; spacing: 7px; padding: 8px; }
QTabWidget::pane { border: 0; background: #ffffff; }
QTabBar::tab { padding: 12px 13px; background: #eef1f6; color: #66758b; }
QTabBar::tab:selected { background: #ffffff; color: #225bc5; border-bottom: 2px solid #3677e8; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #ffffff; border: 0; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #f9fafc; border: 1px solid #d7dee9; border-radius: 5px;
  padding: 6px; min-height: 20px; selection-background-color: #dbe9ff;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
  border: 1px solid #3677e8; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
  color: #929eaf; background: #f1f3f6; border-color: #e4e8ef; }
QPushButton { background: #f6f8fc; border: 1px solid #d5deeb; border-radius: 5px;
  padding: 8px 12px; min-height: 20px; }
QPushButton:hover { background: #eaf1fc; border-color: #a8bfe2; }
QPushButton:pressed { background: #dbe8fa; }
QPushButton:disabled { color: #99a4b4; background: #f1f3f6; }
QPushButton[primary="true"] { background: #2864cf; color: white; border-color: #2864cf; }
QPushButton[primary="true"]:hover { background: #2056b7; }
QPushButton[primary="true"]:disabled { background: #a1b9e5; border-color: #a1b9e5; }
QLabel[role="heading"] { font-size: 19px; font-weight: 600; color: #203149; }
QLabel[role="muted"] { color: #6c7a8e; }
QLabel[role="error"] { color: #b43b44; }
QWidget[role="actionbar"] { background: #ffffff; border-top: 1px solid #dce2eb; }
QTableWidget { background: white; border: 1px solid #dce3ed; gridline-color: #e8edf4;
  selection-background-color: #dceaff; selection-color: #203149; }
QHeaderView::section { background: #f1f4f9; border: 0; padding: 7px; color: #52627a; }
QStatusBar { background: #ffffff; border-top: 1px solid #dce2eb; color: #65748b; }
QToolTip { background: #243247; color: white; border: 0; padding: 6px; }
"""


def heading(text: str, muted: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("role", "muted" if muted else "heading")
    return label


def integer(value: int, low: int, high: int) -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def decimal(value: float, low: float, high: float, suffix: str = "", digits: int = 3):
    widget = QDoubleSpinBox()
    widget.setDecimals(digits)
    widget.setRange(low, high)
    widget.setValue(value)
    widget.setSuffix(suffix)
    return widget


def panel(title: str, description: str):
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(20, 24, 20, 24)
    layout.setSpacing(14)
    layout.addWidget(heading(title))
    layout.addWidget(heading(description, True))
    form = QFormLayout()
    form.setSpacing(12)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.addLayout(form)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll, layout, form


class Worker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    done = Signal()

    def __init__(self, function):
        super().__init__()
        self.function = function

    @Slot()
    def run(self):
        try:
            self.finished.emit(self.function())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.done.emit()


class Tasks(QObject):
    """Own threads until complete; deliver result callbacks on the UI thread."""

    result = Signal(object)
    error = Signal(str)
    idle = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.thread = None
        self.worker = None

    def start(self, function):
        if self.thread is not None:
            raise RuntimeError("Another operation is still running.")
        self.thread = QThread(self)
        self.worker = Worker(function)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.result)
        self.worker.failed.connect(self.error)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.cleanup)
        self.thread.start()

    @Slot()
    def cleanup(self):
        self.thread.deleteLater()
        self.thread = None
        self.worker = None
        self.idle.emit()
