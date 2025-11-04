from PySide6 import QtWidgets, QtCore, QtGui

from splinker.core import gradient_registry, point_editor_registry, Color, Layer
from splinker.widgets import CanvasWidget
from splinker.core.point_editors import PointEditorComponent


class LayerItem(QtWidgets.QWidget):
    """
    One overlay 'row' that contains its own list of points/colors.
    Mirrors the previous PathTab behavior but scoped to a single overlay/spline.
    """
    # Let the row announce activation (e.g., when user clicks "Activate")
    requestActivate = QtCore.Signal(object)  # emits the overlay
    # emit (overlay_obj, new_name) when the title is renamed by the user
    nameEdited = QtCore.Signal(object, str)

    def __init__(self, overlay: CanvasWidget, name: str = "", parent=None):
        super().__init__(parent)
        self._overlay = overlay
        self._block_item_changed = False

        self._layer_name = name
        self._layer_idx = -1

        self._gear = QtWidgets.QToolButton(self)
        self._gear.setText("⋯")
        self._gear.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._gear.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)

        # find layer idx by name
        for i in range(len(self._overlay)):
            if self._overlay[i].name == self._layer_name:
                self._layer_idx = i
                break
        if self._layer_idx < 0:
            try:
                self._layer_idx = self._overlay.get_active_idx()
            except Exception:
                self._layer_idx = 0 if len(self._overlay) > 0 else -1

        self._title = QtWidgets.QLabel(self._layer_name)
        self._title.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self._title_editor: QtWidgets.QLineEdit | None = None  # NEW

        self._list = QtWidgets.QListWidget(self)
        self._list.setUniformItemSizes(True)

        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._title, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        head.addWidget(self._gear, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(head)
        lay.addWidget(self._list)

        self._list.itemChanged.connect(self._on_item_changed)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.itemSelectionChanged.connect(self._activate_self)

        # live refresh with spline changes
        self.overlay.display.pointsChanged.connect(self.refresh)

        menu = QtWidgets.QMenu(self._gear)
        grad_menu = menu.addMenu("Gradient")
        for name, grad_cls in gradient_registry.items():
            act = grad_menu.addAction(name)
            # bind class to action
            act.triggered.connect(lambda _=False, cls=grad_cls: self._apply_registry_gradient(cls))
        spline_menu = menu.addMenu("Spline type")
        for key, editor_cls in point_editor_registry.items():  # dict[str, type[PointEditorComponent]]
            act = spline_menu.addAction(key)
            # bind the registry key to the action
            act.triggered.connect(lambda _=False, k=key: self._apply_point_editor(k))

        self._gear.setMenu(menu)

        self._overlay.overlayUpdated.connect(self._on_overlay_updated)
        self._overlay.layerNameChanged.connect(self._on_layer_name_changed)
        self.installEventFilter(self)
        self.refresh()

    @property
    def layer_name(self) -> str:
        if self._layer_idx < 0 or self._layer_idx >= len(self._overlay):
            return "Overlay"
        return self._overlay[self._layer_idx].name

    @property
    def layer(self) -> Layer:
        if self._layer_idx < 0 or self._layer_idx >= len(self._overlay):
            raise ValueError(self._layer_idx)
        return self._overlay[self._layer_idx]

    @property
    def overlay(self) -> CanvasWidget:
        return self._overlay

    # ----- inline title editing ----------------------------------------
    def eventFilter(self, obj, ev):
        if isinstance(ev, QtGui.QMouseEvent):
            if ev.type() == QtCore.QEvent.Type.MouseButtonPress and ev.button() == QtCore.Qt.MouseButton.LeftButton:
                self._activate_self()
                return True
            if ev.type() == QtCore.QEvent.Type.MouseButtonDblClick and ev.button() == QtCore.Qt.MouseButton.LeftButton:
                self._begin_title_edit()
                return True
        return super().eventFilter(obj, ev)

    def _begin_title_edit(self):
        if self._title_editor is not None:
            return
        # replace the label in-place with a line edit
        self._title_editor = QtWidgets.QLineEdit(self._title.text(), self)
        self._title_editor.setObjectName("layerTitleEditor")
        self._title_editor.setMinimumWidth(self._title.minimumWidth())
        self._title_editor.selectAll()
        self._title_editor.editingFinished.connect(self._commit_title_edit)

        # swap widgets in the header layout
        lay = self._title.parentWidget().layout()
        idx = lay.indexOf(self._title)
        lay.insertWidget(idx, self._title_editor)
        self._title.hide()
        self._title_editor.show()
        self._title_editor.setFocus(QtCore.Qt.FocusReason.MouseFocusReason)

    def _commit_title_edit(self):
        if self._title_editor is None:
            return
        new_name = self._title_editor.text().strip()
        if not new_name:
            new_name = "Overlay"

        self._title.setText(new_name)
        self._layer_name = new_name

        self.nameEdited.emit(self._overlay, new_name)
        self._overlay.set_layer_name(self._layer_idx, new_name)

        # restore label
        self._end_title_edit()

    def _end_title_edit(self):
        if self._title_editor is None:
            return
        self._title.show()
        ed = self._title_editor
        self._title_editor = None
        ed.deleteLater()

    def keyPressEvent(self, ev):
        # allow Esc to cancel an active title edit
        if self._title_editor is not None and ev.key() == QtCore.Qt.Key.Key_Escape:
            self._end_title_edit()
            return
        super().keyPressEvent(ev)

    # ----- data refresh ------------------------------------------------------
    def refresh(self, /):
        if self.layer is None:
            self._list.clear()
            return

        # points
        pts_attr = self.layer.path.points
        pts = pts_attr() if callable(pts_attr) else (pts_attr or [])

        # colors
        colors = self.layer.point_colors()

        self.set_points_and_colors(pts or [], colors)

    def set_points_and_colors(self, pts: list[QtCore.QPointF], colors: list | None, /):
        self._block_item_changed = True
        self._list.clear()
        n = len(pts)
        for i in range(n):
            c = (colors[i] if (colors and i < len(colors)) else None)
            text = self._format_rgb_text(i, c)
            item = QtWidgets.QListWidgetItem(text)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self._apply_item_brushes(item, c)
            item.setData(QtCore.Qt.UserRole, c)  # store QColor (or None)
            self._list.addItem(item)

        add_item = QtWidgets.QListWidgetItem("+ Add point…")
        f = add_item.font()
        f.setBold(True)
        add_item.setFont(f)
        add_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
        add_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        add_item.setData(QtCore.Qt.UserRole, "__adder__")
        self._list.addItem(add_item)

        self._block_item_changed = False

    # ----- formatting & painting --------------------------------------------
    def _format_rgb_text(self, idx: int, color: Color | None, /) -> str:
        if color is None or not color.isValid():
            raise ValueError(color)
            # return f"{idx:02d}: (?, ?, ?)"
        r, g, b = color.to_rgb()
        return f"{idx:02d}: {r}, {g}, {b}"

    def _apply_item_brushes(self, item: QtWidgets.QListWidgetItem, color: Color | None, /):
        if color is None or not color.isValid():
            item.setBackground(QtGui.QBrush())
            item.setForeground(QtGui.QBrush())
            return
        item.setBackground(QtGui.QBrush(color.to_QColor()))
        r, g, b = color.to_rgb()
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        fg = QtGui.QColor(0, 0, 0) if lum > 0.6 else QtGui.QColor(255, 255, 255)
        item.setForeground(QtGui.QBrush(fg))

    # ----- helpers -----------------------------------------------------------
    def _is_adder_item(self, item: QtWidgets.QListWidgetItem, /) -> bool:
        return item is not None and item.data(QtCore.Qt.UserRole) == "__adder__"

    # ----- context menu / add point -----------------------------------------
    def _on_context_menu(self, pos):
        if self.layer is None:
            return
        self._activate_self()
        menu = QtWidgets.QMenu(self)
        act_add = menu.addAction("Add point…")
        act = menu.exec_(self._list.mapToGlobal(pos))
        if act is act_add:
            self._add_point_via_color()

    def _add_point_via_color(self, /):
        if self.layer is None:
            return

        initial = QtGui.QColor(255, 255, 255)
        it = self._list.currentItem()
        if it is not None and not self._is_adder_item(it):
            prev = it.data(QtCore.Qt.UserRole)
            if isinstance(prev, QtGui.QColor) and prev.isValid():
                initial = prev

        color = QtWidgets.QColorDialog.getColor(initial, self, "Choose color")
        if not color.isValid():
            return

        grad = self._overlay[self._layer_idx].gradient
        if grad is None:
            QtWidgets.QMessageBox.warning(self, "Add point", "No gradient available for this layer.")
            return

        pt = grad.point_at(Color.from_qcolor(color))
        if pt is None:
            QtWidgets.QMessageBox.warning(self, "Add point", "Color not found in gradient.")
            return

    # ----- editing handlers --------------------------------------------------
    def _notify(self, text: str):
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), text, self)

    # --- helper: validate color is available in current gradient ----------------
    def _color_supported(self, color: QtGui.QColor) -> bool:
        return self._overlay[self._layer_idx].gradient.point_at(Color.from_qcolor(color)) is not None

    def _apply_color_edit_row(self, idx: int, color: QtGui.QColor):
        if not (isinstance(color, QtGui.QColor) and color.isValid()):
            return
        # validate against gradient
        grad = self._overlay[self._layer_idx].gradient
        pt = grad.point_at(Color.from_qcolor(color))
        if pt is None:
            self._notify("Color not available in this gradient")
            return

        # 1) move the path point on the canvas
        path = self.layer.path
        if 0 <= idx < len(path.points):
            path.edit_point(idx, pt)
            self._overlay.display.update()
            self._overlay.overlayUpdated.emit(self._layer_idx)

        # 2) refresh the row’s item (re-fetch to avoid stale pointer)
        item = self._list.item(idx)
        if item is None or self._is_adder_item(item):
            return
        try:
            self._apply_color_edit(idx, item, color)
        except RuntimeError:
            pass

    def _on_item_double_clicked(self, item: QtWidgets.QListWidgetItem):
        if self.layer is None:
            return
        if self._is_adder_item(item):
            self._add_point_via_color()
            return
        idx = self._list.row(item)
        start = item.data(QtCore.Qt.UserRole)
        initial = start if isinstance(start, QtGui.QColor) else QtGui.QColor(255, 255, 255)
        color = QtWidgets.QColorDialog.getColor(initial, self, "Choose color")
        if not color.isValid():
            return
        self._apply_color_edit_row(idx, color)

    def _on_item_changed(self, item: QtWidgets.QListWidgetItem):
        if self._block_item_changed or self.layer is None or self._is_adder_item(item):
            return
        idx = self._list.row(item)
        txt = item.text()
        parts = [p.strip() for p in txt.split(":")[-1].split(",")]
        if len(parts) != 3:
            self._revert_item(idx, item)
            return
        try:
            r, g, b = (max(0, min(255, int(v))) for v in parts)
        except Exception:
            self._revert_item(idx, item)
            return
        color = QtGui.QColor(r, g, b)
        if not color.isValid() or not self._color_supported(color):
            self._notify("Color not available in this gradient")
            self._revert_item(idx, item)
            return
        # re-fetch item to avoid stale pointer
        fresh = self._list.item(idx)
        if fresh is None or self._is_adder_item(fresh):
            return
        try:
            self._apply_color_edit(idx, fresh, color)
        except RuntimeError:
            # list rebuilt meanwhile; nothing to do
            pass

    def _apply_color_edit(self, idx: int, item: QtWidgets.QListWidgetItem, color: QtGui.QColor, /):
        self._block_item_changed = True
        item.setData(QtCore.Qt.UserRole, color)
        item.setText(self._format_rgb_text(idx, color))
        self._apply_item_brushes(item, color)
        self._block_item_changed = False

    def _revert_item(self, idx: int, item: QtWidgets.QListWidgetItem, /):
        if self._is_adder_item(item):
            return
        prev = item.data(QtCore.Qt.UserRole)
        self._block_item_changed = True
        item.setText(self._format_rgb_text(idx, prev if isinstance(prev, QtGui.QColor) else None))
        self._apply_item_brushes(item, prev if isinstance(prev, QtGui.QColor) else None)
        self._block_item_changed = False

    def setName(self, name: str):
        """Set the row title without emitting nameEdited (avoids feedback loops)."""
        nm = (name or "").strip() or "Overlay"
        # Update the label
        self._layer_name = nm
        self._title.setText(self._layer_name)
        # If inline editor is active, keep it in sync too
        if self._title_editor is not None:
            self._title_editor.blockSignals(True)
            self._title_editor.setText(self._layer_name)
            self._title_editor.blockSignals(False)

    @QtCore.Slot(int)
    def _on_overlay_updated(self, idx: int):
        if idx == self._layer_idx:
            self.refresh()

    @QtCore.Slot(int)
    def _on_layer_name_changed(self, idx: int):
        if idx == self._layer_idx:
            name = self._overlay[idx].name or "Overlay"
            self.setName(name)

    def _activate_self(self):
        self._overlay.set_active_layer(self._layer_idx)
        self.requestActivate.emit(self)

    def _apply_registry_gradient(self, grad_cls):
        """
        Instantiate the selected gradient class using its own defaults,
        and apply it to the active layer.
        """
        layer_widget: LayerOverlayWidget = self._overlay[self._layer_idx]
        layer_widget.set_gradient(grad_cls())
        self.requestActivate.emit(self)

    def _apply_point_editor(self, key: str):
        """
        Switch the active layer's point editor to the given registry key.
        Converts the current path to the new editor (best-effort fit), updates UI,
        and emits overlayUpdated so dependents refresh.
        """
        # Resolve editor class
        editor_cls = point_editor_registry[key]
        # Build editor instance
        new_editor: PointEditorComponent = editor_cls()

        self.layer.path.set_point_editor(new_editor)
        self.layer.update()

        # Notify observers (left bar list, gradient bar, etc.)
        self._overlay.overlayUpdated.emit(self._layer_idx)
