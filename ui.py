from typing import AnyStr, Optional
import os
import sys
import time
import pychromecast
import zeroconf

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QSlider, QVBoxLayout, QHBoxLayout, QFileDialog, \
    QMessageBox, QComboBox, QStyle, QSpacerItem, QSizePolicy, QLabel
from pychromecast.controllers.media import MediaController

from server import Server


def showError(title, message, icon=QMessageBox.Critical):
    print(f'ERROR! {title}\n{message}', file=sys.stderr)
    msgBox = QMessageBox()
    msgBox.setIcon(icon)
    msgBox.setText(message)
    msgBox.setWindowTitle(title)
    msgBox.setStandardButtons(QMessageBox.Ok)
    #msgBox.buttonClicked.connect(msgButtonClick)

    returnValue = msgBox.exec()
    #if returnValue == QMessageBox.Ok:
        #print('OK clicked')


def getDefaultIcon(name: AnyStr, context: QWidget) -> QIcon:
    pixmapi = getattr(QStyle, name)
    icon: QIcon = context.style().standardIcon(pixmapi)
    return icon


class QMediaControl(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.min: int = 0
        self.max: Optional[int] = None

        self.v_layout = QVBoxLayout()
        self.h_layout = QHBoxLayout()

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.play = QPushButton(getDefaultIcon('SP_MediaPlay', self), "", self)
        self.pause = QPushButton(getDefaultIcon('SP_MediaPause', self), "", self)
        self.stop = QPushButton(getDefaultIcon('SP_MediaStop', self), "", self)
        self.time_label = QLabel("--/--", self)

        self.slider.setDisabled(True)
        self.slider.setTracking(False)

        self.v_layout.addWidget(self.slider)
        self.v_layout.addLayout(self.h_layout)
        self.h_layout.addWidget(self.play)
        self.h_layout.addWidget(self.pause)
        self.h_layout.addWidget(self.stop)
        self.h_layout.addItem(QSpacerItem(20, 1, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.h_layout.addWidget(self.time_label)

        self.setLayout(self.v_layout)

        self.slider.rangeChanged.connect(self.rangeChanged)
        self.slider.valueChanged.connect(self.updateLabel)

    def setDisabled(self, disabled: bool) -> None:
        self.slider.setDisabled(disabled)
        self.pause.setDisabled(disabled)
        self.stop.setDisabled(disabled)

    def rangeChanged(self, min: int, max: int):
        self.min = min
        self.max = max
        self.updateLabel()

    def updateLabel(self):
        if self.max is None:
            text = '--/--'
        else:
            text = f'{self.slider.value()}/{self.max}'
        self.time_label.setText(text)


class QWidgetChromecast(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.layout = QHBoxLayout()
        self.combobox = QComboBox()

        self.layout.addWidget(self.combobox)
        self.setLayout(self.layout)

        self.services = None
        self.browser = None

        self.zconf = None
        self.device = None
        self.cast = None
        self.media_controller: Optional[MediaController] = None
        self.httpserver = None

        self.discover_chromecasts()

    def discover_chromecasts(self):
        # List chromecasts on the network, but don't connect
        print("Searching for chromcast devices...")
        services, browser = pychromecast.discovery.discover_chromecasts()
        self.services = services
        self.browser = browser
        print("Search complete")
        # shut down discovery
        self.browser.stop_discovery()

        if len(services) == 0:
            showError("No chromecast found!",
                      "Check if the chromecast and the your device are on the same network and disable the firewall")
            sys.exit(-1)

        selection = []
        for i, (uuid, device) in enumerate(browser.devices.items()):
            selection.append(uuid)
            self.combobox.addItem(f'{device.model_name} - {device.friendly_name}', uuid)

    def is_connected(self):
        return self.cast is not None

    def connect_chromecast(self):
        if self.zconf is None:
            self.zconf = zeroconf.Zeroconf()

        selected_uuid = self.combobox.currentData()
        print("selected uuid = ", selected_uuid)
        self.device = self.browser.devices[selected_uuid]

        print(f"Connecting to {self.device.friendly_name}")
        self.cast = pychromecast.get_chromecast_from_cast_info(
            self.device,
            self.zconf,
        )

        # Discover and connect to chromecasts named Living Room
        # chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=["Living Room TV"])
        # a = [cc.device.friendly_name for cc in chromecasts]
        # print(a)

        # Start worker thread and wait for cast device to be ready
        self.cast.wait()
        print(self.cast.device)
        print(self.cast.status)
        self.media_controller = self.cast.media_controller
        return self.cast

    def play_file(self, filename: AnyStr):
        assert self.is_connected()

        self.httpserver = Server(filename)
        self.httpserver.start()

        time.sleep(1)
        self.media_controller.play_media(self.httpserver.serving_url(), 'video/mp4')
        self.media_controller.block_until_active()

        print(self.media_controller.status)


class UI(QWidget):
    app: QApplication
    play_button: QPushButton
    stop_button: QPushButton
    playback_slider: QMediaControl

    filename: AnyStr

    def __init__(self, app: QApplication):
        super().__init__()
        self.filename = ""
        self.app = app
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timer_check)
        self.timer.start(1000)
        self.old_seek_time: float = -1

        self.media_select = QPushButton('Select media', self)
        self.playback_slider = QMediaControl(self)
        self.chromecast_ui = QWidgetChromecast(self)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.chromecast_ui)
        self.layout.addWidget(self.media_select)
        self.layout.addWidget(self.playback_slider)
        self.setLayout(self.layout)
        self.show()

        self.media_select.clicked.connect(self.select_file)
        self.playback_slider.play.clicked.connect(self.play)
        self.playback_slider.pause.clicked.connect(self.pause)
        self.playback_slider.stop.clicked.connect(self.stop)
        self.playback_slider.slider.sliderMoved.connect(self.shadow_seek)
        self.playback_slider.slider.sliderReleased.connect(self.seek)
        self.seek_command = 0
        # self.playback_slider.valu

    def select_file(self):
        print("selecting file")
        # dialog = QFileDialog(self, 'Open streaming source')
        # dialog.setFileMode(QFileDialog.AnyFile)
        # dialog.setFilter("Text files (*.mkv)")
        home = os.environ['HOME']
        selection = QFileDialog\
            .getOpenFileName(self, 'Open streaming source',
                             home, "Video files (*.mp4 *.mkv *.ogg *.webm)")
        if selection[0] == '':
            return
        self.filename = selection[0]
        self.media_select.setText(self.filename)

    def play(self):
        print("play")
        if not self.chromecast_ui.is_connected():
            if self.filename == "":
                showError("Invalid file","Please select a file first")
                return
            self.chromecast_ui.connect_chromecast()
            self.chromecast_ui.play_file(self.filename)
            self.playback_slider.setDisabled(False)
        else: # self.chromecast_ui.media_controller.status.player_is_playing:
            self.chromecast_ui.media_controller.play()

    def pause(self):
        if self.chromecast_ui.media_controller is not None:
            self.chromecast_ui.media_controller.pause()

    def stop(self):
        print("stop")
        if not self.chromecast_ui.is_connected():
            showError("Error", "Chromecast not playing")
            return
        self.chromecast_ui.media_controller.stop()
        self.playback_slider.setDisabled(True)

    def shadow_seek(self, new_value):
        self.seek_command = new_value

    def seek(self):
        value: int = self.playback_slider.slider.value()
        print(f'seek at {value}/{self.seek_command} - min={self.playback_slider.slider.minimum()} max={self.playback_slider.slider.maximum()}')
        # if self.playback_slider.slider.isSliderDown():
        self.chromecast_ui.media_controller.seek(float(self.seek_command))

    def timer_check(self):
        if self.chromecast_ui.media_controller is None:
            return
        media_status = self.chromecast_ui.media_controller.status
        # print(media_status)
        if media_status.duration is not None:
            self.playback_slider.slider.setMaximum(int(media_status.duration))
            self.playback_slider.setDisabled(False)
            # print(media_status.current_time)
            new_seek_value = self.playback_slider.slider.value()
            if media_status.player_state == 'PLAYING':
                new_seek_value += 1
            if media_status.current_time != self.old_seek_time:
                self.old_seek_time = media_status.current_time
                new_seek_value = media_status.current_time
            if not self.playback_slider.slider.isSliderDown():
                self.playback_slider.slider.setValue(new_seek_value)

    def exec(self):
        self.app.exec()
        if self.chromecast_ui.media_controller is not None:
            self.chromecast_ui.media_controller.stop()
        if self.chromecast_ui.httpserver is not None:
            self.chromecast_ui.httpserver.stop()
