from abc import ABC
from PySide6 import QtWidgets



class ABCQtMeta(type(QtWidgets.QWidget), type(ABC)):
    pass