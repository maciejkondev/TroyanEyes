from PySide6.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        
        # Style
        self.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 5px;
                font-size: 13px;
            }
            QListWidget::item {
                background-color: #3a3a3a;
                padding: 8px;
                margin-bottom: 4px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #5e9cff;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #474747;
            }
            QListWidget::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #555;
                background-color: #2a2a2a;
                margin-right: 10px;
            }
            QListWidget::indicator:checked {
                background-color: #4CAF50;
                border: 1px solid #4CAF50;
            }
            QListWidget::indicator:unchecked {
                background-color: #2a2a2a;
            }
            QListWidget::indicator:checked:hover {
                background-color: #45a049;
            }
        """)

    def add_item(self, text, checked=True):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.addItem(item)

    def get_items(self):
        """Returns a list of text for all items."""
        items = []
        for i in range(self.count()):
            items.append(self.item(i).text())
        return items

    def get_checked_items(self):
        """Returns a list of text for only checked items."""
        items = []
        for i in range(self.count()):
            item = self.item(i)
            if item.checkState() == Qt.Checked:
                items.append(item.text())
        return items

    def get_state(self):
        """Returns a list of dicts with 'name' and 'checked' status."""
        state = []
        for i in range(self.count()):
            item = self.item(i)
            state.append({
                "name": item.text(),
                "checked": item.checkState() == Qt.Checked
            })
        return state

    def set_state(self, state):
        """Populates list from a list of dicts."""
        self.clear()
        for item_data in state:
            self.add_item(item_data["name"], item_data.get("checked", True))
