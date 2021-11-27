#!/usr/bin/env python3

import os.path
import time
from typing import AnyStr

import pychromecast
import zeroconf
from PyQt5.QtWidgets import QApplication

from server import Server
from ui import UI


def main():
    app = QApplication([])
    gui = UI(app)
    gui.exec()
    return


if __name__ == "__main__":
    main()
