import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTextEdit, QTreeView, QPushButton, QMenu, QAbstractItemView,
    QItemDelegate, QComboBox, QSpinBox, QDoubleSpinBox,
    QFileDialog, QMessageBox, QToolTip, QStyle, QFrame,
    QTabWidget, QLabel,
)
from PySide6.QtGui import (
    QIcon, QAction, QStandardItem, QStandardItemModel, QKeySequence, QShortcut,
    QFontDatabase, QTextCursor, QTextOption, QCursor, QBrush, QColor,
)
from PySide6.QtCore import Qt, Signal, QItemSelectionModel, QLocale, QEvent, QSettings

QLocale.setDefault(QLocale(QLocale.C))

from typing import List
import Command
import DataType
import ThrowData


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
    "HITBOX":                        ["damage", "angle"],
    "WAIT":                          ["time"],
    "AFTER":                         ["time"],
    "LOOP_START":                    ["iterations"],
    "PLAY_SFX":                      ["sfx"],
    "PLAY_FGM_STORE":                ["sfx"],
    "VOICE_SFX":                     ["sfx"],
    "PLAY_LOOP_SFX":                 ["sfx"],
    "PLAY_LOOP_VOICE":               ["sfx"],
    "SMASH_VOICE":                   ["sfx"],
    "GFX":                           ["effect", "bone"],
    "GFX_ITEM":                      ["effect", "bone"],
    "SWORD_TRAIL":                   ["command"],
    "SET_SLOPE_CONTOUR_STATE":       ["state"],
    "SET_SPECIFIC_HURTBOX_STATE":    ["part", "state"],
    "SET_ALL_HURTBOX_STATE":         ["state"],
    "SET_HURTBOX_STATE":             ["state"],
    "CLEAR_HITBOX":                  ["hitbox_id"],
    "SET_HITBOX_DAMAGE":             ["attack_id", "damage"],
    "SET_HITBOX_SIZE":               ["attack_id", "size"],
    "SET_FRAME_SPEED_MULTIPLIER":    ["fsm"],
    "SET_ARMOR":                     ["value"],
    "TOPJOINT_TRANSLATION_MULTI":    ["value"],
    "SET_Y_VEL":                     ["value"],
    "FAST_FALL":                     ["enabled"],
    "SET_KINETIC_STATE":             ["state"],
    "SET_HITBOX_FGM":                ["hitbox_id", "fgm_id"],
    "SET_HITBOX_HITLAG_MULT":        ["hitbox_id", "multiplier"],
    "SET_HITBOX_DI_MULT":            ["hitbox_id", "multiplier"],
    "OVERRIDE_HITBOX_DIRECTION":     ["hitbox_id", "direction"],
    "GO_TO_MOVESET_FILE":            ["offset"],
    "L_VOICE_SFX":                   ["sfx", "alt_sfx"],
    "RANDOM_SFX":                    ["chance", "sfx_type"],
    "SET_TEXTURE_PART":              ["part", "index"],
}


# LOOP_START/LOOP_END get a fixed accent instead of the auto-assigned palette
# color, so loop boundaries stand out in both the tree and the hex view.
_LOOP_COLORS = ("#7a5c00", "#ffe9a8")


def _dim_color(fg_hex: str, bg_hex: str, t: float = 0.55) -> str:
    """Blend fg toward bg, for secondary/low-emphasis text like the frame column."""
    fg = QColor(fg_hex)
    bg = QColor(bg_hex)
    r = round(fg.red()   * (1 - t) + bg.red()   * t)
    g = round(fg.green() * (1 - t) + bg.green() * t)
    b = round(fg.blue()  * (1 - t) + bg.blue()  * t)
    return f'#{r:02x}{g:02x}{b:02x}'


def get_command_color(cmd) -> tuple:
    key = type(cmd).__name__
    if key in ("LOOP_START", "LOOP_END"):
        return _LOOP_COLORS
    if key not in _type_color_cache:
        _type_color_cache[key] = _COLOR_PALETTE[len(_type_color_cache) % len(_COLOR_PALETTE)]
    return _type_color_cache[key]


# Loops are genuinely simulated pass-by-pass (see _simulate_range) rather than
# computed with a single-pass-times-iterations shortcut, because that
# shortcut is wrong whenever a loop body contains AFTER: ftmain.c computes
# `script_wait = value - anim_frame`, so on the 2nd+ pass through the same
# AFTER, anim_frame is often already at (or past) the target and the "wait"
# costs 0 frames — it's only a real delay on the first pass. Simulating for
# real handles that automatically, for both display and the running total
# carried past the loop.
_LOOP_SIM_CAP = 1000    # cap simulated passes per loop; guards against a huge/corrupt iteration count hanging the GUI
_FRAME_DISPLAY_CAP = 8  # cap how many per-pass frame numbers are shown per row


def _find_matching_loop_end(commands, start_idx: int, limit: int) -> int:
    """Bracket-match: index of the LOOP_END that closes commands[start_idx]
    (a LOOP_START), searching only within [start_idx, limit)."""
    depth = 0
    for j in range(start_idx, limit):
        if isinstance(commands[j], Command.LOOP_START):
            depth += 1
        elif isinstance(commands[j], Command.LOOP_END):
            depth -= 1
            if depth == 0:
                return j
    return limit - 1  # malformed/unmatched; fall back rather than crash


def _simulate_range(commands, start: int, end: int, running: int):
    """Simulate commands[start:end] once, starting at frame `running`.
    Returns (frames_by_index, end_running), where frames_by_index maps each
    visited command's index to the list of frames it executed on (more than
    one entry when it sits inside a loop that got expanded below it)."""
    frames_by_index: dict = {}
    i = start
    while i < end:
        cmd = commands[i]
        frames_by_index.setdefault(i, []).append(running)
        if isinstance(cmd, Command.WAIT):
            running += cmd.time.value
            i += 1
        elif isinstance(cmd, Command.AFTER):
            running = cmd.time.value
            i += 1
        elif isinstance(cmd, Command.LOOP_START):
            body_start = i + 1
            body_end = _find_matching_loop_end(commands, i, end)
            iterations = min(cmd.iterations.value, _LOOP_SIM_CAP)
            for _ in range(iterations):
                sub_frames, running = _simulate_range(commands, body_start, body_end, running)
                for idx, flist in sub_frames.items():
                    frames_by_index.setdefault(idx, []).extend(flist)
                # LOOP_END is the per-pass loop-check; it runs once per pass too
                frames_by_index.setdefault(body_end, []).append(running)
            i = body_end + 1
        else:
            i += 1
    return frames_by_index, running


def compute_layout(commands: List["Command.BaseCommand"]):
    """Compute, per top-level command:
    - the list of frame numbers it executes on — one entry per pass through
      any loop(s) it sits inside (a single entry otherwise);
    - its loop nesting depth (LOOP_START/LOOP_END sit at their loop's
      enclosing depth; everything between them is one level deeper).

    Frames start counting at 1 (the first frame of the script). WAIT
    (SyncWait) is relative (`script_wait += value`); AFTER (AsyncWait) is an
    absolute jump to frame `value` (`script_wait = value - anim_frame`).
    """
    depths: List[int] = []
    depth = 0
    loop_stack = []
    for cmd in commands:
        closes_loop = isinstance(cmd, Command.LOOP_END) and loop_stack
        if closes_loop:
            depth -= 1
            loop_stack.pop()
        depths.append(depth)
        if isinstance(cmd, Command.LOOP_START):
            loop_stack.append(True)
            depth += 1

    frames_by_index, _ = _simulate_range(commands, 0, len(commands), 1)
    frame_lists = [frames_by_index.get(i, [1]) for i in range(len(commands))]
    return frame_lists, depths


def format_command_label(comm, depth: int = 0) -> str:
    summary = get_command_summary(comm)
    indent = "» " * depth
    return f"{indent}{comm._hex[0:2].upper()}  {comm.command_name}{summary}"


def format_frame_label(frames=None) -> str:
    """compute_layout returns 1-indexed frame numbers per pass; join them,
    e.g. "11,13,15" for a command inside a 3-iteration loop."""
    if not frames:
        return ""
    shown = ",".join(f"{f:02d}" for f in frames[:_FRAME_DISPLAY_CAP])
    return shown + "…" if len(frames) > _FRAME_DISPLAY_CAP else shown


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
    editingStarted = Signal()
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
        self.editingStarted.emit()
        self.display_mode = False
        raw = ''.join(c for c in self.toPlainText() if c in '0123456789abcdefABCDEF').upper()
        # Show with a space every 8 chars for readability; _get_raw_hex strips them back out
        spaced = ' '.join(raw[i:i+8] for i in range(0, len(raw), 8))
        self.blockSignals(True)
        self.setPlainText(spaced)
        self.blockSignals(False)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.editingFinished.emit()


def _parse_number(text: str):
    """Parse a user-typed number: decimal, 0x hex, or bare hex (e.g. '1A').
    Returns an int or None if unparseable."""
    t = text.strip()
    try:
        return int(t, 0)       # handles 0x prefix and plain decimal
    except ValueError:
        pass
    try:
        return int(t, 16)      # bare hex without 0x, e.g. "1A" or "FF"
    except ValueError:
        return None


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
        if attr is None:
            return

        if isinstance(editor, QSpinBox):
            attr.SetValue(editor.value())
            item.setText(str(editor.value()))
        elif isinstance(editor, QDoubleSpinBox):
            attr.SetValue(editor.value())
            item.setText(str(editor.value()))
        elif isinstance(editor, QComboBox):
            text = editor.currentText().strip()
            label_val = attr.GetLabelValue(text)
            if label_val is not None:
                attr.SetValue(label_val)
                item.setText(text)
            else:
                val = _parse_number(text)
                if val is not None:
                    attr.SetValue(val)
                    item.setText(attr.GetLabel())
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
        self.undo_stack: List[str] = []
        self.redo_stack: List[str] = []
        self.current_file_path: str | None = None
        self.settings = QSettings()
        self.last_directory = self.settings.value("last_directory", os.path.expanduser("~"))
        self.remix_log_path = self.settings.value("remix_log_path", "")
        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 1200, 720)
        self.setWindowTitle("SSB64 Moveset Editor")

        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        central_widget = QWidget()
        self.tabs.addTab(central_widget, "Moveset")
        layout = QHBoxLayout(central_widget)

        # ── Hex viewer ──────────────────────────────────────────────
        self.binary_text = HexTextEdit(self)
        self.binary_text.setAcceptRichText(True)
        # This widget's own undo/redo would otherwise swallow Ctrl+Z/Ctrl+Y
        # before our app-level undo (which operates on the whole command list,
        # not text edits) ever sees them.
        self.binary_text.setUndoRedoEnabled(False)
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
        # Command (column 0) keeps owning the expand/collapse branches and the
        # field children, regardless of where it's displayed — see
        # _apply_column_layout(), which moves the Frame column to the front.
        self.tree.setTreePosition(0)
        tree_layout.addWidget(self.tree)
        layout.addWidget(tree_col)

        # ── Sidebar buttons ──────────────────────────────────────────
        self.toolcol = QWidget()
        tool_layout = QVBoxLayout(self.toolcol)
        tool_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        tool_layout.setSpacing(4)
        layout.addWidget(self.toolcol)

        sp = QStyle.StandardPixmap
        add_button       = _sidebar_button("Add",       "Add command after selection",  sp.SP_FileDialogNewFolder)
        duplicate_button = _sidebar_button("Duplicate", "Duplicate selected command",    sp.SP_FileDialogDetailedView)
        delete_button    = _sidebar_button("Delete",    "Delete selected command",       sp.SP_TrashIcon)
        move_up_btn      = _sidebar_button("Up",        "Move selected command up",      sp.SP_ArrowUp)
        move_dn_btn      = _sidebar_button("Down",      "Move selected command down",    sp.SP_ArrowDown)
        self.undo_btn    = _sidebar_button("Undo",      "Undo last change",              sp.SP_ArrowBack)
        self.redo_btn    = _sidebar_button("Redo",      "Redo last undone change",       sp.SP_ArrowForward)

        submenu = QMenu(self)
        for comm_code, comm_class in Command.COMMANDS.items():
            act = QAction(f"{comm_code} – {comm_class.command_name}", self)
            act.setData((comm_code, comm_class))
            act.triggered.connect(self.on_add_command)
            submenu.addAction(act)
        add_button.setMenu(submenu)

        duplicate_button.clicked.connect(self.duplicate_selected_command)
        delete_button.clicked.connect(self.delete_selected_command)
        move_up_btn.clicked.connect(self.move_command_up)
        move_dn_btn.clicked.connect(self.move_command_down)
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn.clicked.connect(self.redo)
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)

        # Only fires when the tree itself has focus (not an inline field editor),
        # so pressing Delete while editing a value still deletes text as normal.
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.tree)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(self.delete_selected_command)

        for btn in (add_button, duplicate_button, delete_button, move_up_btn, move_dn_btn):
            tool_layout.addWidget(btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        tool_layout.addWidget(sep)

        for btn in (self.undo_btn, self.redo_btn):
            tool_layout.addWidget(btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        tool_layout.addWidget(sep2)

        # ── Menu bar ─────────────────────────────────────────────────
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        load_remix_action = QAction("Load Remix Output Log...", self)
        load_remix_action.triggered.connect(self.load_remix_output_log)
        file_menu.addAction(load_remix_action)

        edit_menu = menubar.addMenu("Edit")
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)

        # ── Signal wiring ────────────────────────────────────────────
        self.binary_text.textChanged.connect(self.update_decoded_data)
        self.binary_text.editingFinished.connect(lambda: self._refresh_hex_display())
        self.binary_text.editingStarted.connect(self._push_undo)
        self.binary_text.command_hovered.connect(self.show_command_tooltip)
        self.binary_text.command_clicked.connect(self.on_hex_command_clicked)
        self.tree.model().dataChanged.connect(self.on_tree_data_changed)
        self.tree.selectionModel().selectionChanged.connect(self.on_tree_selection_changed)

        self.binary_text.setPlainText(
            "bc0000030800000498787c00003c0000000000000000000008000010500000000c01c23000b4000000"
            "000000e986400300400f000c81e23000f00032000000005a46400300400f0098004c0000000000ff6a"
            "0000000000004c000029040000051800000000000000"
        )

        self._build_throw_tab()

    def _build_throw_tab(self):
        """THROWF_DATA.bin / THROWB_DATA.bin editor — a fixed 56-byte struct,
        unrelated to the moveset command stream, so it gets its own simple
        tab: two groups of 7 fields (Thrown, Grab Release) instead of a
        command tree. See ThrowData.py for the file format."""
        self.throw_data: ThrowData.ThrowDataFile | None = None
        self.throw_file_path: str | None = None

        throw_widget = QWidget()
        throw_layout = QVBoxLayout(throw_widget)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        open_btn = QPushButton("Open...")
        save_btn = QPushButton("Save")
        save_as_btn = QPushButton("Save As...")
        open_btn.clicked.connect(self.open_throw_file)
        save_btn.clicked.connect(self.save_throw_file)
        save_as_btn.clicked.connect(self.save_throw_file_as)
        for b in (open_btn, save_btn, save_as_btn):
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        throw_layout.addWidget(btn_row)

        self.throw_path_label = QLabel("No file open")
        throw_layout.addWidget(self.throw_path_label)

        self.throw_tree = QTreeView()
        self.throw_tree.setModel(QStandardItemModel())
        self.throw_tree.setHeaderHidden(False)
        self.throw_tree.setItemDelegate(self.delegate)
        self.throw_tree.setItemsExpandable(False)  # Thrown/Grab Release always stay open
        throw_layout.addWidget(self.throw_tree)

        self.tabs.addTab(throw_widget, "Throw Data")

    def _populate_throw_tree(self):
        model = self.throw_tree.model()
        model.clear()
        model.setHorizontalHeaderLabels(["Field", "Value"])
        if self.throw_data is None:
            return

        for group_name, desc in (("Thrown", self.throw_data.thrown),
                                  ("Grab Release", self.throw_data.grab_release)):
            group_item = QStandardItem(group_name)
            group_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for field_name, label, _dtype in ThrowData.FIELDS:
                attr = desc.values[field_name]
                name_item = QStandardItem(label)
                name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                value_item = CustomStandardItem(str(attr.value))
                value_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable)
                value_item.setData(attr, Qt.ItemDataRole.UserRole)
                if attr.template is not None:
                    value_item.setText(attr.GetLabel())
                group_item.appendRow([name_item, value_item])
            model.appendRow(group_item)

        # Thrown / Grab Release groups always stay open — there are only 2
        # of them and 7 fields each, no reason to make the user dig for them.
        self.throw_tree.expandAll()
        self.throw_tree.resizeColumnToContents(0)

    def open_throw_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Throw Data", self.last_directory, "Binary Files (*.bin);;All Files (*)")
        if not file_path:
            return
        with open(file_path, "rb") as f:
            data = f.read()
        self.throw_data = ThrowData.ThrowDataFile(data.hex().upper())
        self.throw_file_path = file_path
        self.throw_path_label.setText(file_path)
        self._remember_directory(file_path)
        self._populate_throw_tree()

    def save_throw_file(self):
        if self.throw_file_path:
            self._write_throw_to(self.throw_file_path)
        else:
            self.save_throw_file_as()

    def save_throw_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Throw Data", self.last_directory, "Binary Files (*.bin);;All Files (*)")
        if file_path and self._write_throw_to(file_path):
            self.throw_file_path = file_path
            self.throw_path_label.setText(file_path)
            self._remember_directory(file_path)

    def _write_throw_to(self, file_path: str) -> bool:
        if self.throw_data is None:
            return False
        try:
            with open(file_path, "wb") as f:
                f.write(self.throw_data.ToBytes())
            return True
        except OSError as e:
            QMessageBox.critical(self, "Save Error", f"Could not save: {e}")
            return False

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

    def _build_tree_item(self, comm: Command.BaseCommand, frames: List[int] = None, depth: int = 0) -> List[QStandardItem]:
        """Returns the 3 column items for one top-level command row: [Command,
        Value (unused at this level), Frame]. Command stays the structural
        column-0 item that owns the field children (see setTreePosition(0) in
        initUI) so every existing `.item(row, 0)` lookup keeps working."""
        bg, fg = get_command_color(comm)

        cmd_item = QStandardItem(format_command_label(comm, depth))
        cmd_item.setFlags(Qt.ItemFlag.NoItemFlags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        cmd_item.setBackground(QBrush(QColor(bg)))
        cmd_item.setForeground(QBrush(QColor(fg)))
        cmd_item.setData(comm)

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
                cmd_item.appendRow([child0, child1])

        value_item = QStandardItem("")
        value_item.setFlags(Qt.ItemFlag.NoItemFlags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        value_item.setBackground(QBrush(QColor(bg)))

        frame_item = QStandardItem(format_frame_label(frames))
        frame_item.setFlags(Qt.ItemFlag.NoItemFlags | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        frame_item.setBackground(QBrush(QColor(bg)))
        frame_item.setForeground(QBrush(QColor(_dim_color(fg, bg))))
        frame_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return [cmd_item, value_item, frame_item]

    # ── Data flow ─────────────────────────────────────────────────────

    def update_decoded_data(self):
        if self._updating:
            return
        self._updating = True
        binary_data = self._get_raw_hex()
        try:
            self.tree.model().clear()
            self.tree.model().setHorizontalHeaderLabels(["Command", "Value", "Frame"])
            self.commands = BinaryFileViewer.parse_moveset_file(binary_data)
            frame_lists, depths = compute_layout(self.commands)
            for comm, flist, depth in zip(self.commands, frame_lists, depths):
                self.tree.model().appendRow(self._build_tree_item(comm, flist, depth))
            self.tree.resizeColumnToContents(0)
            self.tree.resizeColumnToContents(2)
            self._apply_column_layout()
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
        self._refresh_command_labels()
        self._refresh_hex_display()

    def _refresh_command_labels(self):
        """Recompute frame numbers and loop depth for every top-level row.
        Needed on any edit, since a WAIT/LOOP change shifts everything after it.
        Blocks model signals: setText() on an item already in the model fires
        dataChanged, which would otherwise re-enter on_tree_data_changed."""
        frame_lists, depths = compute_layout(self.commands)
        model = self.tree.model()
        model.blockSignals(True)
        try:
            for row, (comm, flist, depth) in enumerate(zip(self.commands, frame_lists, depths)):
                cmd_item = model.item(row, 0)
                if cmd_item:
                    cmd_item.setText(format_command_label(comm, depth))
                frame_item = model.item(row, 2)
                if frame_item:
                    frame_item.setText(format_frame_label(flist))
        finally:
            model.blockSignals(False)

    def _apply_column_layout(self):
        """Move the Frame column (logical 2) to visual position 0, i.e. the
        left edge, without disturbing which column (0, Command) structurally
        owns the tree's branches/children — see setTreePosition(0) above."""
        header = self.tree.header()
        visual = header.visualIndex(2)
        if visual != 0:
            header.moveSection(visual, 0)

    def on_tree_data_changed(self, topLeft, bottomRight, roles=None):
        if self._updating:
            return
        self._push_undo()
        self.export_data()

    # ── Undo / redo ──────────────────────────────────────────────────

    def _push_undo(self):
        """Snapshot the current state before a mutation. Call this right
        before the change happens, not after."""
        if not self.commands:
            return
        self.undo_stack.append(self._get_raw_hex())
        del self.undo_stack[:-100]
        self.redo_stack.clear()
        self._update_undo_redo_actions()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._get_raw_hex())
        hex_str = self.undo_stack.pop()
        self.binary_text.setPlainText(hex_str)
        self._update_undo_redo_actions()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._get_raw_hex())
        hex_str = self.redo_stack.pop()
        self.binary_text.setPlainText(hex_str)
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        self.undo_btn.setEnabled(bool(self.undo_stack))
        self.redo_btn.setEnabled(bool(self.redo_stack))

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

        self._push_undo()

        selected = self.tree.selectionModel().currentIndex()
        if selected.isValid():
            top_row = selected.parent().row() if selected.parent().isValid() else selected.row()
            insert_row = top_row + 1
        else:
            insert_row = self.tree.model().rowCount()

        self.tree.model().insertRow(insert_row, self._build_tree_item(comm))
        self.export_data()

    def duplicate_selected_command(self):
        selected = self.tree.selectionModel().currentIndex()
        if not selected.isValid():
            return
        row = selected.parent().row() if selected.parent().isValid() else selected.row()
        item = self.tree.model().item(row, 0)
        comm = item.data() if item else None
        if comm is None:
            return

        self._push_undo()

        dup = type(comm)(comm.ToHex())
        self.tree.model().insertRow(row + 1, self._build_tree_item(dup))
        new = self.tree.model().index(row + 1, 0)
        self.tree.selectionModel().setCurrentIndex(
            new, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.export_data()

    def delete_selected_command(self):
        selected = self.tree.selectionModel().currentIndex()
        if not selected.isValid():
            return
        self._push_undo()
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
        self._push_undo()
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
        self._push_undo()
        item = self.tree.model().takeRow(row)[0]
        self.tree.model().insertRow(row + 1, item)
        new = self.tree.model().index(row + 1, 0)
        self.tree.selectionModel().setCurrentIndex(
            new, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.export_data()

    # ── File I/O ──────────────────────────────────────────────────────

    def _remember_directory(self, file_path: str):
        self.last_directory = os.path.dirname(file_path)
        self.settings.setValue("last_directory", self.last_directory)

    def _set_current_file(self, file_path: str):
        self.current_file_path = file_path
        self._remember_directory(file_path)
        self.setWindowTitle(f"SSB64 Moveset Editor — {os.path.basename(file_path)}")

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Binary File", self.last_directory, "Binary Files (*.bin);;All Files (*)")
        if file_path:
            with open(file_path, "rb") as f:
                self.binary_text.setPlainText(f.read().hex().upper())
            self.undo_stack.clear()
            self.redo_stack.clear()
            self._update_undo_redo_actions()
            self._set_current_file(file_path)

    def save_file(self):
        """Save over the currently open file, or prompt if none is open yet."""
        if self.current_file_path:
            self._write_hex_to(self.current_file_path)
        else:
            self.save_file_as()

    def save_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Binary File", self.last_directory, "Binary Files (*.bin);;All Files (*)")
        if file_path and self._write_hex_to(file_path):
            self._set_current_file(file_path)

    def _write_hex_to(self, file_path: str) -> bool:
        hex_str = self._get_raw_hex()
        try:
            with open(file_path, "wb") as f:
                f.write(bytes.fromhex(hex_str))
            return True
        except ValueError as e:
            QMessageBox.critical(self, "Save Error", f"Invalid hex data: {e}")
            return False

    def _load_remix_data(self, path: str = None) -> bool:
        """Load extra Remix IDs (SFX, GFX, etc.) from a build output log.
        Uses the saved path if one was picked before, else falls back to
        ./output.log for anyone still using the old symlink-in-place setup."""
        path = path or self.remix_log_path or "./output.log"
        ok = DataType.LoadRemixStuff(path)
        if not ok:
            QMessageBox.warning(
                self, "Warning",
                f"Could not read a Remix output log at '{path}'. Build Remix with output "
                "redirected to a file, then use File → Load Remix Output Log... to point "
                "the editor at it, to load additional Remix IDs for SFX, GFX, etc."
            )
        return ok

    def load_remix_output_log(self):
        start_dir = os.path.dirname(self.remix_log_path) if self.remix_log_path else self.last_directory
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Remix Output Log", start_dir, "Log Files (*.log);;All Files (*)")
        if not file_path:
            return
        if self._load_remix_data(file_path):
            self.remix_log_path = file_path
            self.settings.setValue("remix_log_path", file_path)
            QMessageBox.information(self, "Remix Data Loaded", f"Loaded Remix IDs from:\n{file_path}")

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
    app.setOrganizationName("ssb64-moveset-editor")
    app.setApplicationName("MovesetEditor")
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
    viewer._load_remix_data()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
