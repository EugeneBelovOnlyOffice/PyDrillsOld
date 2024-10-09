from PyQt6 import QtCore


def fmon():
    @QtCore.pyqtSlot(str)
    def directory_changed(path):
        print("Directory Changed!!!")

    @QtCore.pyqtSlot(str)
    def file_changed(path):
        print("File Changed!!!")

    fs_watcher = QtCore.QFileSystemWatcher(["./"])

    fs_watcher.connect(
        fs_watcher, QtCore.SIGNAL("directoryChanged(QString)"), directory_changed
    )
    fs_watcher.connect(fs_watcher, QtCore.SIGNAL("fileChanged(QString)"), file_changed)
