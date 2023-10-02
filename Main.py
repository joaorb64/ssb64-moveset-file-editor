import sys
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
import traceback

from typing import NamedTuple, Dict, List
from enum import Enum, auto
from dataclasses import dataclass
from abc import ABC, abstractmethod

import Command
import DataType


class CustomDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        item = index.model().itemFromIndex(index)

        if item.parent():
            comm: Command = item.parent().data()

        attr: DataType.BASE_TYPE = item.data(Qt.UserRole)

        if attr and attr.template != None:
            editor: QComboBox = QComboBox(parent)

            for k, v in attr.template.items():
                editor.addItem(k, v)
            editor.setEditable(True)
        else:
            editor: QSpinBox = QSpinBox(parent)
            editor.setRange(-65535, 65535)
            # editor = super().createEditor(parent, option, index)
        return editor

    def setEditorData(self, editor, index):
        item = index.model().itemFromIndex(index)
        if isinstance(editor, QLineEdit):
            editor.setText(item.text())
        elif isinstance(editor, QSpinBox):
            editor.setValue(int(item.text()))
        elif isinstance(editor, QComboBox):
            editor.setCurrentText(editor.currentText())
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        item = index.model().itemFromIndex(index)
        attr = item.data(Qt.UserRole)

        print("Edit", editor, attr)

        if isinstance(editor, QSpinBox):
            attr.SetValue(editor.value())
            item.setText(editor.text())
        elif isinstance(editor, QComboBox):
            item.setText(editor.currentText())
            attr.SetValue(attr.GetLabelValue(editor.currentText()))
            print(attr.value)
        else:
            super().setModelData(editor, model, index)

    def closeEditor(self, editor, hint):
        super().closeEditor(editor, hint)


class CustomStandardItem(QStandardItem):
    def __init__(self, text, delegate_type=None):
        super().__init__(text)
        if delegate_type:
            self.setData(delegate_type, Qt.UserRole)


class BinaryFileViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle("Binary File Viewer")

        # Create a central widget with a vertical layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout()

        # Create a TextEdit widget for binary data
        self.binary_text = QTextEdit(self)
        layout.addWidget(self.binary_text)

        # Create a TextEdit widget for decoded data
        self.tree = QTreeView(self)
        layout.addWidget(self.tree)

        self.tree.setModel(QStandardItemModel())
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.setHeaderHidden(False)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.delegate = CustomDelegate()
        self.tree.setItemDelegate(self.delegate)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.toolcol = QWidget()
        self.toolcol.setLayout(QVBoxLayout())
        self.toolcol.layout().setAlignment(Qt.AlignTop)

        layout.addWidget(self.toolcol)

        # Create buttons with default arrow icons for moving entries up and down
        add_button = QPushButton(QIcon.fromTheme(
            "list-add"), "", self)
        self.toolcol.layout().addWidget(add_button)

        submenu = QMenu(self)

        for comm_code, comm_class in Command.COMMANDS.items():
            act = QAction(f"{comm_code} - {comm_class.command_name}", self)
            submenu.addAction(act)

        # Associate the submenu with the button
        add_button.setMenu(submenu)

        # Create QPushButton for deleting an item from the list with a system "Delete" icon
        delete_button = QPushButton(QIcon.fromTheme(
            "edit-delete"), "", self)
        self.toolcol.layout().addWidget(delete_button)

        move_up_button = QPushButton(QIcon.fromTheme("go-up"), "", self)
        self.toolcol.layout().addWidget(move_up_button)

        move_down_button = QPushButton(QIcon.fromTheme("go-down"), "", self)
        self.toolcol.layout().addWidget(move_down_button)

        # Connect button click events to move functions
        move_up_button.clicked.connect(self.move_command_up)
        move_down_button.clicked.connect(self.move_command_down)

        # Create "Open" and "Save" buttons
        # open_button = QPushButton("Open", self)
        # open_button.clicked.connect(self.open_file)
        # layout.addWidget(open_button)

        # save_button = QPushButton("Save", self)
        # save_button.clicked.connect(self.save_file)
        # layout.addWidget(save_button)

        central_widget.setLayout(layout)

        # Create a menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')

        # Add "Open" and "Save" actions to the menu
        open_action = QAction('Open', self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction('Save', self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        # Connect the binary_text's textChanged signal to update_decoded_data
        self.binary_text.textChanged.connect(self.update_decoded_data)

        self.tree.model().dataChanged.connect(self.export_data)

        self.binary_text.setText(
            "bc0000030800000498787c00003c0000000000000000000008000010500000000c01c23000b40000000000005a46400300400f000c81e23000f00032000000005a46400300400f0098004c0000000000ff6a0000000000004c000029040000051800000000000000")

    def move_command_up(self):
        selected_index = self.tree.selectionModel().currentIndex()
        # Check if a valid item is selected and it's not in the first row
        if selected_index.isValid() and selected_index.row() > 0:
            # Get the items to swap
            current_item = self.tree.model().itemFromIndex(selected_index)

            # Swap the items in the model
            self.tree.model().takeRow(selected_index.row())
            self.tree.model().insertRow(
                selected_index.row() - 1, [current_item])

            # Update the selection to the newly moved item
            new_index = self.tree.model().index(
                selected_index.row() - 1, selected_index.column())
            self.tree.selectionModel().clearSelection()
            self.tree.selectionModel().setCurrentIndex(
                new_index, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def move_command_down(self):
        pass

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open Binary File', '', 'Binary Files (*.bin);;All Files (*)')
        if file_path:
            with open(file_path, 'rb') as file:
                binary_data = file.read()
                self.binary_text.setPlainText(binary_data.hex().upper())
                self.update_decoded_data()

    def save_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Binary File', '', 'Binary Files (*.bin);;All Files (*)')
        if file_path:
            with open(file_path, 'wb') as file:
                binary_data = self.binary_text.toPlainText().encode('utf-8')
                file.write(binary_data)

    def update_decoded_data(self):
        binary_data = self.binary_text.toPlainText()

        try:
            print("Rebuild tree")
            # model = QStandardItemModel()
            # model.setHorizontalHeaderLabels(['Parameter', 'Value'])

            self.tree.model().clear()
            self.tree.model().setHorizontalHeaderLabels(['Parameter', 'Value'])
            # self.tree.setModel(model)

            # self.delegate = CustomDelegate()
            # self.tree.setItemDelegate(self.delegate)

            comms: List[Command.BaseCommand] = BinaryFileViewer.parse_moveset_file(
                binary_data)

            for com in comms:
                parent = QStandardItem(com._hex[0:2] + " " + com.command_name)
                parent.setFlags(Qt.NoItemFlags |
                                Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                for k, v in com.__dict__.items():
                    if isinstance(v, DataType.BASE_TYPE):
                        child0 = QStandardItem(k)
                        child0.setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)
                        child1 = CustomStandardItem(str(v.value))
                        child1.setFlags(Qt.ItemIsEnabled |
                                        Qt.ItemIsEditable | Qt.ItemIsSelectable)
                        parent.appendRow([child0, child1])
                        child1.setData(v, Qt.UserRole)

                        if v.template != None:
                            child1.setText(v.GetLabel())

                self.tree.model().appendRow(parent)
                parent.setData(com)

            print(self.tree.model().rowCount())
        except:
            traceback.print_exc()

    def export_data(self):
        finalStr = ""
        for row in range(self.tree.model().rowCount()):
            item = self.tree.model().item(row, 0)
            print(item.data().ToHex())
            finalStr += item.data().ToHex()
        print(finalStr)

    def parse_moveset_file(moveset: str):
        commands = []

        pos = 0

        while pos < len(moveset):
            hx = moveset[pos:pos+2].upper()
            commclass = Command.GetCommand(hx)
            comm = commclass(moveset[pos:pos+commclass.command_size])

            if isinstance(comm, Command.UNKNOWN):
                comm.command_name = hx

            commands.append(comm)
            pos += commclass.command_size

        return commands


def main():
    app = QApplication(sys.argv)
    viewer = BinaryFileViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
