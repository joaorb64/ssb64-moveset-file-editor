import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTextEdit, QTreeView, QPushButton, QMenu, QAbstractItemView,
    QItemDelegate, QComboBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QMessageBox, QToolTip, QStyle, QFrame,
)
from PySide6.QtGui import (
    QIcon, QAction, QStandardItem, QStandardItemModel,
    QFontDatabase, QTextCursor, QTextOption, QCursor, QBrush, QColor,
)
from PySide6.QtCore import Qt, Signal, QItemSelectionModel, QLocale, QEvent

QLocale.setDefault(QLocale(QLocale.C))

from typing import List
import Command
import DataType


# Each command type gets a stable color derived from its class name on first use.
_COLOR_PALETTE = [
    ("#1a3a5c", "#c8e0ff"),
    ("#1a5c3a", "#c8ffdf"),
    ("#5c3a1a", "#ffd8b0"),
    ("#3a1a5c", "#e0c8ff"),
    ("#5c1a3a", "#ffc8df"),
    ("#1a5c5c", "#c8ffff"),
    ("#5c5c1a", "#ffffc8"),
    ("#3a3a5c", "#c8c8ff"),
]
_type_color_cache: dict = {}

SELECTED_BG = "#b84c00"
SELECTED_FG = "#ffffff"

# Short field names to show in tree parent row and tooltip header.
SUMMARY_FIELDS = {
    "HITBOX":                    ["damage", "base_knockback", "angle"],
    "WAIT":                      ["time"],
    "AFTER":                     ["time"],
    "LOOP_START":                ["iterations"],
    "PLAY_SFX":                  ["sfx"],
    "VOICE_SFX":                 ["sfx"],
    "GFX":                       ["effect"],
    "SWORD_TRAIL":               ["command"],
    "SET_SLOPE_CONTOUR_STATE":   ["state"],
    "SET_SPECIFIC_HURTBOX_STATE": ["part", "state"],
    "SET_FRAME_SPEED_MULTIPLIER": ["fsm"],
}


def get_command_color(cmd) -> tuple:
    key = type(cmd).__name__
    if key not in _type_color_cache:
        _type_color_cache[key] = _COLOR_PALETTE[len(_type_color_cache) % len(_COLOR_PALETTE)]
    return _type_color_cache[key]


def get_command_summary(cmd) -> str:
    fields = SUMMARY_FIELDS.get(type(cmd).__name__, [])
    parts = []
    for f in fields:
        v = getattr(cmd, f, None)
        if isinstance(v, DataType.BASE_TYPE):
            label = v.GetLabel() if v.template else str(v.value)
            parts.append(f"{f}:{label}")
    return "  · " + "  ".join(parts) if parts else ""


class HexTextEdit(QTextEdit):
    editingFinished = Signal()
    command_hovered = Signal(int)
    command_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.display_mode = False
        self._last_hover_idx = -1
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.viewport() and self.display_mode:
            t = event.type()
            if t == QEvent.Type.MouseMove:
                anchor = self.anchorAt(event.position().toPoint())
                idx = int(anchor[4:]) if anchor.startswith("cmd:") else -1
                if idx != self._last_hover_idx:
                    self._last_hover_idx = idx
                    self.command_hovered.emit(idx)
            elif t == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                anchor = self.anchorAt(event.position().toPoint())
                if anchor.startswith("cmd:"):
                    try:
                        self.command_clicked.emit(int(anchor[4:]))
                    except ValueError:
                        pass
        return super().eventFilter(obj, event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.display_mode = False
        raw = ''.join(c for c in self.toPlainText() if c in '0123456789abcdefABCDEF').upper()
        self.blockSignals(True)
        self.setPlainText(raw)
        self.blockSignals(False)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editingFinished.emit()


class CustomDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        item = index.model().itemFromIndex(index)
        attr: DataType.BASE_TYPE = item.data(Qt.UserRole)

        if attr and attr.template is not None:
            editor = QComboBox(parent)
            for k, v in attr.template.items():
                editor.addItem(k, v)
            editor.setEditable(True)
        elif isinstance(attr, DataType.FLOAT32):
            editor = QDoubleSpinBox(parent)
            editor.setRange(-65535, 65535)
            editor.setDecimals(6)
        else:
            editor = QSpinBox(parent)
            editor.setRange(-65535, 65535)
        return editor

    def setEditorData(self, editor, index):
        item = index.model().itemFromIndex(index)
        if isinstance(editor, QSpinBox):
            try:
                editor.setValue(int(item.text()))
            except ValueError:
                pass
        elif isinstance(editor, QDoubleSpinBox):
            try:
                editor.setValue(float(item.text()))
            except ValueError:
                pass
        elif isinstance(editor, QComboBox):
            editor.setCurrentText(item.text())
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        item = index.model().itemFromIndex(index)
        attr = item.data(Qt.UserRole)

        if isinstance(editor, QSpinBox):
            attr.SetValue(editor.value())
            item.setText(str(editor.value()))
        elif isinstance(editor, QDoubleSpinBox):
            attr.SetValue(editor.value())
            item.setText(str(editor.value()))
        elif isinstance(editor, QComboBox):
            item.setText(editor.currentText())
            attr.SetValue(attr.GetLabelValue(editor.currentText()))
        else:
            super().setModelData(editor, model, index)


class CustomStandardItem(QStandardItem):
    def __init__(self, text, delegate_type=None):
        super().__init__(text)
        if delegate_type:
            self.setData(delegate_type, Qt.UserRole)


def _sidebar_button(text: str, tooltip: str, sp: "QStyle.StandardPixmap | None" = None) -> QPushButton:
    """Create a consistently-sized sidebar button."""
    if sp is not None:
        btn = QPushButton(QApplication.style().standardIcon(sp), text)
    else:
        btn = QPushButton(text)
    btn.setToolTip(tooltip)
    btn.setMinimumWidth(110)
    return btn


class BinaryFileViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.commands: List[Command.BaseCommand] = []
        self._updating = False
        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 1200, 720)
        self.setWindowTitle("SSB64 Moveset Editor")

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # ── Hex viewer ──────────────────────────────────────────────
        self.binary_text = HexTextEdit(self)
        self.binary_text.setAcceptRichText(True)
        self.binary_text.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.binary_text.setMinimumWidth(300)
        self.binary_text.setMaximumWidth(460)
        fnt = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fnt.setPointSize(10)
        self.binary_text.setFont(fnt)
        layout.addWidget(self.binary_text)

        # ── Tree view ────────────────────────────────────────────────
        tree_col = QWidget()
        tree_layout = QVBoxLayout(tree_col)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(2)

        tree_buttons = QWidget()
        tree_btn_layout = QHBoxLayout(tree_buttons)
        tree_btn_layout.setContentsMargins(0, 0, 0, 0)
        tree_btn_layout.setSpacing(4)
        expand_btn = QPushButton("Expand All")
        expand_btn.setToolTip("Expand all commands")
        collapse_btn = QPushButton("Collapse All")
        collapse_btn.setToolTip("Collapse all commands")
        expand_btn.clicked.connect(lambda: self.tree.expandAll())
        collapse_btn.clicked.connect(lambda: self.tree.collapseAll())
        tree_btn_layout.addWidget(expand_btn)
        tree_btn_layout.addWidget(collapse_btn)
        tree_layout.addWidget(tree_buttons)

        self.tree = QTreeView(self)
        self.tree.setModel(QStandardItemModel())
        self.tree.setAlternatingRowColors(False)
        self.tree.setHeaderHidden(False)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.delegate = CustomDelegate()
        self.tree.setItemDelegate(self.delegate)
        self.tree.setUniformRowHeights(False)
        tree_layout.addWidget(self.tree)
        layout.addWidget(tree_col)

        # ── Sidebar buttons ──────────────────────────────────────────
        self.toolcol = QWidget()
        tool_layout = QVBoxLayout(self.toolcol)
        tool_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        tool_layout.setSpacing(4)
        layout.addWidget(self.toolcol)

        sp = QStyle.StandardPixmap
        add_button    = _sidebar_button("Add",    "Add command after selection",  sp.SP_FileDialogNewFolder)
        delete_button = _sidebar_button("Delete", "Delete selected command",      sp.SP_TrashIcon)
        move_up_btn   = _sidebar_button("Up",     "Move selected command up",     sp.SP_ArrowUp)
        move_dn_btn   = _sidebar_button("Down",   "Move selected command down",   sp.SP_ArrowDown)

        submenu = QMenu(self)
        for comm_code, comm_class in Command.COMMANDS.items():
            act = QAction(f"{comm_code} – {comm_class.command_name}", self)
            act.setData((comm_code, comm_class))
            act.triggered.connect(self.on_add_command)
            submenu.addAction(act)
        add_button.setMenu(submenu)

        delete_button.clicked.connect(self.delete_selected_command)
        move_up_btn.clicked.connect(self.move_command_up)
        move_dn_btn.clicked.connect(self.move_command_down)

        for btn in (add_button, delete_button, move_up_btn, move_dn_btn):
            tool_layout.addWidget(btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        tool_layout.addWidget(sep)

        # ── Menu bar ─────────────────────────────────────────────────
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        # ── Signal wiring ────────────────────────────────────────────
        self.binary_text.textChanged.connect(self.update_decoded_data)
        self.binary_text.editingFinished.connect(lambda: self._refresh_hex_display())
        self.binary_text.command_hovered.connect(self.show_command_tooltip)
        self.binary_text.command_clicked.connect(self.on_hex_command_clicked)
        self.tree.model().dataChanged.connect(self.export_data)
        self.tree.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)

        self.binary_text.setPlainText(
            "bc0000030800000498787c00003c0000000000000000000008000010500000000c01c23000b4000000"
            "000000e986400300400f000c81e23000f00032000000005a46400300400f0098004c0000000000ff6a"
            "0000000000004c000029040000051800000000000000"
        )

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_raw_hex(self) -> str:
        return ''.join(c for c in self.binary_text.toPlainText()
                       if c in '0123456789abcdefABCDEF').upper()

    def _build_hex_html(self, selected_idx: int = -1) -> str:
        parts = []
        for i, cmd in enumerate(self.commands):
            if i == selected_idx:
                bg, fg = SELECTED_BG, SELECTED_FG
            else:
                bg, fg = get_command_color(cmd)
            hex_str = cmd.ToHex().upper()
            words = [hex_str[j:j+8] for j in range(0, len(hex_str), 8)]
            inner = '&nbsp;'.join(words)
            parts.append(
                f'<a href="cmd:{i}" style="color:{fg};text-decoration:none;">'
                f'<span style="background-color:{bg};color:{fg};'
                f'padding:1px 4px;border-radius:2px;">{inner}</span>'
                f'</a>'
            )
        body = '&nbsp; '.join(parts)
        return (
            '<html><body style="background-color:#111827;margin:4px;">'
            '<p style="font-family:monospace;font-size:10pt;line-height:2em;">'
            f'{body}</p></body></html>'
        )

    def _refresh_hex_display(self, selected_idx: int = -1):
        if not self.commands:
            return
        html = self._build_hex_html(selected_idx)
        self.binary_text.display_mode = True
        self.binary_text.blockSignals(True)
        self.binary_text.setHtml(html)
        self.binary_text.blockSignals(False)

    def _build_tree_item(self, comm: Command.BaseCommand) -> QStandardItem:
        bg, fg = get_command_color(comm)
        summary = get_command_summary(comm)
        label = f"{comm._hex[0:2].upper()}  {comm.command_name}{summary}"
        parent = QStandardItem(label)
        parent.setFlags(Qt.ItemFlag.NoItemFlags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        parent.setBackground(QBrush(QColor(bg)))
        parent.setForeground(QBrush(QColor(fg)))
        parent.setData(comm)

        for k, v in comm.__dict__.items():
            if k.startswith('_'):
                continue
            if isinstance(v, DataType.BASE_TYPE):
                child0 = QStandardItem(k)
                child0.setFlags(Qt.ItemFlag.NoItemFlags | Qt.ItemFlag.ItemIsEnabled)
                child1 = CustomStandardItem(str(v.value))
                child1.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
                child1.setData(v, Qt.ItemDataRole.UserRole)
                if v.template is not None:
                    child1.setText(v.GetLabel())
                parent.appendRow([child0, child1])

        return parent

    # ── Data flow ─────────────────────────────────────────────────────

    def update_decoded_data(self):
        if self._updating:
            return
        self._updating = True
        binary_data = self._get_raw_hex()
        try:
            self.tree.model().clear()
            self.tree.model().setHorizontalHeaderLabels(["Command", "Value"])
            self.commands = BinaryFileViewer.parse_moveset_file(binary_data)
            for comm in self.commands:
                self.tree.model().appendRow(self._build_tree_item(comm))
            self.tree.resizeColumnToContents(0)
        except Exception:
            traceback.print_exc()
        finally:
            self._updating = False

        if not self.binary_text.hasFocus():
            self._refresh_hex_display()

    def export_data(self):
        if self._updating:
            return
        self.commands = []
        for row in range(self.tree.model().rowCount()):
            item = self.tree.model().item(row, 0)
            if item and item.data():
                self.commands.append(item.data())
        self._refresh_hex_display()

    # ── Tooltip ───────────────────────────────────────────────────────

    def show_command_tooltip(self, idx: int):
        if idx < 0 or idx >= len(self.commands):
            QToolTip.hideText()
            return
        cmd = self.commands[idx]
        accent, _ = get_command_color(cmd)
        rows_html = ""
        for k, v in cmd.__dict__.items():
            if k.startswith('_'):
                continue
            if isinstance(v, DataType.BASE_TYPE):
                label = v.GetLabel() if v.template else str(v.value)
                rows_html += (
                    f"<tr>"
                    f"<td style='padding:2px 10px 2px 0;'><i>{k}</i></td>"
                    f"<td style='padding:2px 0;'><b>{label}</b></td>"
                    f"</tr>"
                )
        table = f"<table>{rows_html}</table>" if rows_html else ""
        tip = (
            f"<html>"
            f"<b>{cmd.command_name}</b>"
            f"&nbsp;&nbsp;<span style='color:#aaaaaa;font-size:10px;'>{cmd._hex[0:2].upper()}</span>"
            f"<hr style='margin:4px 0;'>"
            f"{table}"
            f"</html>"
        )
        QToolTip.showText(QCursor.pos(), tip, self.binary_text)

    def on_hex_command_clicked(self, idx: int):
        """Select the corresponding tree row when a hex block is clicked."""
        if 0 <= idx < self.tree.model().rowCount():
            index = self.tree.model().index(idx, 0)
            self.tree.selectionModel().setCurrentIndex(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect |
                       QItemSelectionModel.SelectionFlag.Rows)
            self.tree.scrollTo(index)

    def on_tree_selection_changed(self, selected, deselected):
        if self._updating:
            return
        indexes = selected.indexes()
        if not indexes:
            return
        idx = indexes[0]
        row = idx.parent().row() if idx.parent().isValid() else idx.row()
        self._refresh_hex_display(selected_idx=row)

    # ── Toolbar actions ───────────────────────────────────────────────

    def on_add_command(self):
        action = self.sender()
        comm_code, comm_class = action.data()
        default_hex = comm_code + '0' * (comm_class.command_size - 2)
        try:
            comm = comm_class(default_hex)
        except Exception:
            traceback.print_exc()
            return

        selected = self.tree.selectionModel().currentIndex()
        if selected.isValid():
            top_row = selected.parent().row() if selected.parent().isValid() else selected.row()
            insert_row = top_row + 1
        else:
            insert_row = self.tree.model().rowCount()

        self.tree.model().insertRow(insert_row, [self._build_tree_item(comm)])
        self.export_data()

    def delete_selected_command(self):
        selected = self.tree.selectionModel().currentIndex()
        if not selected.isValid():
            return
        row = selected.parent().row() if selected.parent().isValid() else selected.row()
        self.tree.model().removeRow(row)
        self.export_data()

    def move_command_up(self):
        idx = self.tree.selectionModel().currentIndex()
        if not idx.isValid():
            return
        if idx.parent().isValid():
            idx = self.tree.model().indexFromItem(self.tree.model().itemFromIndex(idx.parent()))
        row = idx.row()
        if row <= 0:
            return
        item = self.tree.model().takeRow(row)[0]
        self.tree.model().insertRow(row - 1, item)
        new = self.tree.model().index(row - 1, 0)
        self.tree.selectionModel().setCurrentIndex(
            new, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.export_data()

    def move_command_down(self):
        idx = self.tree.selectionModel().currentIndex()
        if not idx.isValid():
            return
        if idx.parent().isValid():
            idx = self.tree.model().indexFromItem(self.tree.model().itemFromIndex(idx.parent()))
        row = idx.row()
        if row >= self.tree.model().rowCount() - 1:
            return
        item = self.tree.model().takeRow(row)[0]
        self.tree.model().insertRow(row + 1, item)
        new = self.tree.model().index(row + 1, 0)
        self.tree.selectionModel().setCurrentIndex(
            new, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.export_data()

    # ── File I/O ──────────────────────────────────────────────────────

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Binary File", "", "Binary Files (*.bin);;All Files (*)")
        if file_path:
            with open(file_path, "rb") as f:
                self.binary_text.setPlainText(f.read().hex().upper())

    def save_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Binary File", "", "Binary Files (*.bin);;All Files (*)")
        if file_path:
            hex_str = self._get_raw_hex()
            try:
                with open(file_path, "wb") as f:
                    f.write(bytes.fromhex(hex_str))
            except ValueError as e:
                QMessageBox.critical(self, "Save Error", f"Invalid hex data: {e}")

    # ── Parser ────────────────────────────────────────────────────────

    @staticmethod
    def parse_moveset_file(moveset: str) -> List[Command.BaseCommand]:
        commands = []
        pos = 0
        while pos < len(moveset):
            hx = moveset[pos:pos+2].upper()
            commclass = Command.GetCommand(hx)
            if pos + commclass.command_size > len(moveset):
                break
            comm = commclass(moveset[pos:pos+commclass.command_size])
            if isinstance(comm, Command.UNKNOWN):
                comm.command_name = hx
            commands.append(comm)
            pos += commclass.command_size
        return commands


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QToolTip {
            background-color: #1e2030;
            color: #f0f0f0;
            border: 1px solid #555;
            padding: 4px 6px;
            font-size: 11px;
        }
    """)
    viewer = BinaryFileViewer()
    viewer.show()

    res = DataType.LoadRemixStuff()
    if res is False:
        QMessageBox.warning(
            viewer, "Warning",
            "No output.log found. Build Remix with output redirected to a file and place it "
            "in this program's directory to load additional Remix IDs for SFX, GFX, etc."
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
