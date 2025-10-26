from PySide6 import QtWidgets, QtCore, QtGui

class PathTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._spline: QtWidgets.QWidget | None = None
        self._list = QtWidgets.QListWidget(self)
        self._list.setUniformItemSizes(True)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self._list)

        self._list.itemChanged.connect(self._on_item_changed)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._block_item_changed = False  # guard during programmatic updates

        # Optional: also allow context menu add
        self._list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

    def set_spline(self, spline, /):
        """
        Accepts the spline overlay widget (must expose `.points()` and ideally `.point_colors()`).
        """
        self._spline = spline
        # If overlay emits pointsChanged, keep list live
        sig = getattr(spline, "pointsChanged", None)
        if sig is not None and hasattr(sig, "connect"):
            try:
                sig.connect(self.refresh)
            except Exception:
                pass

    # ----- data refresh ------------------------------------------------------
    def refresh(self, /):
        if self._spline is None:
            self._list.clear()
            return

        # Get points
        pts = getattr(self._spline, "points", None)
        if callable(pts):
            pts = self._spline.points()
        pts = pts or []

        # Get colors if possible
        colors = None
        pc = getattr(self._spline, "point_colors", None)
        if callable(pc):
            try:
                colors = self._spline.point_colors()
            except Exception:
                colors = None

        self.set_points_and_colors(pts, colors)

    def set_points_and_colors(self, pts: list[QtCore.QPointF], colors: list | None, /):
        self._block_item_changed = True
        self._list.clear()
        n = len(pts)
        for i in range(n):
            c = (colors[i] if (colors and i < len(colors)) else None)
            text = self._format_rgb_text(i, c)
            item = QtWidgets.QListWidgetItem(text)
            # Make editable
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            # Paint the row with its color (if any)
            self._apply_item_brushes(item, c)
            # Store original color text for revert if edit fails
            item.setData(QtCore.Qt.UserRole, c)  # store QColor (or None)
            self._list.addItem(item)

        # --- append adder row ------------------------------------------------
        add_item = QtWidgets.QListWidgetItem("+ Add point…")
        f = add_item.font()
        f.setBold(True)
        add_item.setFont(f)
        add_item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignCenter))
        # enabled + selectable, but NOT editable
        add_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        # mark as special
        add_item.setData(QtCore.Qt.UserRole, "__adder__")
        self._list.addItem(add_item)

        self._block_item_changed = False

    # ----- formatting & painting --------------------------------------------
    def _format_rgb_text(self, idx: int, color: QtGui.QColor | None, /) -> str:
        if color is None or not color.isValid():
            return f"{idx:02d}: (?, ?, ?)"
        r, g, b = color.red(), color.green(), color.blue()
        return f"{idx:02d}: {r}, {g}, {b}"

    def _apply_item_brushes(self, item: QtWidgets.QListWidgetItem, color: QtGui.QColor | None, /):
        if color is None or not color.isValid():
            item.setBackground(QtGui.QBrush())
            item.setForeground(QtGui.QBrush())
            return
        item.setBackground(QtGui.QBrush(color))
        # Choose readable text color based on luminance
        r, g, b = color.redF(), color.greenF(), color.blueF()
        # sRGB luminance approx
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        fg = QtGui.QColor(0, 0, 0) if lum > 0.6 else QtGui.QColor(255, 255, 255)
        item.setForeground(QtGui.QBrush(fg))

    # ----- helpers -----------------------------------------------------------
    def _is_adder_item(self, item: QtWidgets.QListWidgetItem, /) -> bool:
        return item is not None and item.data(QtCore.Qt.UserRole) == "__adder__"

    # ----- context menu / add point -----------------------------------------
    def _on_context_menu(self, pos):
        if self._spline is None:
            return
        menu = QtWidgets.QMenu(self)
        act_add = menu.addAction("Add point…")
        act = menu.exec_(self._list.mapToGlobal(pos))
        if act is act_add:
            self._add_point_via_color()

    def _add_point_via_color(self, /):
        if self._spline is None:
            return

        # Start color: use selected row's color if available
        initial = QtGui.QColor(255, 255, 255)
        it = self._list.currentItem()
        if it is not None and not self._is_adder_item(it):
            prev = it.data(QtCore.Qt.UserRole)
            if isinstance(prev, QtGui.QColor) and prev.isValid():
                initial = prev

        color = QtWidgets.QColorDialog.getColor(initial, self, "Choose color")
        if not color.isValid():
            return

        # Map color -> point using the gradient if available
        grad = getattr(self._spline, "_gradient", None)
        mapper = None
        if grad is not None:
            mapper = getattr(grad, "point_for_color", None)
            if not callable(mapper):
                mapper = getattr(grad, "locate_color", None)
        if not callable(mapper):
            mapper = getattr(self._spline, "point_for_color", None)
            if not callable(mapper):
                mapper = getattr(self._spline, "locate_color", None)
        if not callable(mapper):
            QtWidgets.QMessageBox.warning(self, "Add point", "Cannot map color to a point.")
            return

        pt = mapper(color)
        if pt is None:
            QtWidgets.QMessageBox.warning(self, "Add point", "Color not found in gradient.")
            return

        # Insert (keep convex if closed), else append
        inserted = False
        try_insert = getattr(self._spline, "_insert_point_convex", None)
        is_closed = bool(getattr(self._spline, "_closed", False))
        if callable(try_insert) and is_closed:
            try:
                inserted = bool(try_insert(QtCore.QPointF(pt)))
            except Exception:
                inserted = False
        if not inserted:
            plist = getattr(self._spline, "_points", None)
            if isinstance(plist, list):
                plist.append(QtCore.QPointF(pt))
                inserted = True
        if not inserted:
            QtWidgets.QMessageBox.warning(self, "Add point", "Failed to add point to spline.")
            return

        # Update overlay and refresh list
        try:
            self._spline.update()
        except Exception:
            pass
        self.refresh()

    # ----- editing handlers --------------------------------------------------
    def _on_item_double_clicked(self, item: QtWidgets.QListWidgetItem):
        if self._spline is None:
            return
        if self._is_adder_item(item):
            self._add_point_via_color()
            return

        idx = self._list.row(item)
        start = item.data(QtCore.Qt.UserRole)
        if isinstance(start, QtGui.QColor):
            initial = start
        else:
            initial = QtGui.QColor(255, 255, 255)

        color = QtWidgets.QColorDialog.getColor(initial, self, "Choose color")
        if not color.isValid():
            return
        self._apply_color_edit(idx, item, color)

    def _on_item_changed(self, item: QtWidgets.QListWidgetItem):
        if self._block_item_changed or self._spline is None or self._is_adder_item(item):
            return
        idx = self._list.row(item)
        # Expect text like "03: 255, 120, 30" or "255,120,30"
        txt = item.text()
        # Extract last three integers in range 0..255
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
        self._apply_color_edit(idx, item, color)

    def _apply_color_edit(self, idx: int, item: QtWidgets.QListWidgetItem, color: QtGui.QColor, /):
        mover = getattr(self._spline, "move_point_to_color", None)
        ok = bool(callable(mover) and mover(idx, color))
        if not ok:
            # Could not realize the color -> revert
            self._revert_item(idx, item)
            return
        # Success: recolor row and update stored value & text
        self._block_item_changed = True
        item.setData(QtCore.Qt.UserRole, color)
        item.setText(self._format_rgb_text(idx, color))
        self._apply_item_brushes(item, color)
        self._block_item_changed = False

    def _revert_item(self, idx: int, item: QtWidgets.QListWidgetItem, /):
        # If someone tries to edit the adder, ignore silently
        if self._is_adder_item(item):
            return
        prev = item.data(QtCore.Qt.UserRole)
        self._block_item_changed = True
        item.setText(self._format_rgb_text(idx, prev if isinstance(prev, QtGui.QColor) else None))
        self._apply_item_brushes(item, prev if isinstance(prev, QtGui.QColor) else None)
        self._block_item_changed = False
