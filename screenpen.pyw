#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Simple pen
# Author:       Robert Susik
# License:      MIT
# Email:        robert.susik@gmail.com
# ----------------------------------------------------------------------------

import sys
from datetime import datetime
from matplotlib.backends.backend_qt5 import ToolbarQt
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMainWindow, QApplication, QDesktopWidget
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QToolBar, QAction, QDialog, QToolButton, QMenu
from PyQt5.QtGui import (
    QIcon, QScreen, QPalette, QColor, QCursor,
    QSyntaxHighlighter, QPixmap, QKeySequence
)


from PyQt5.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QLabel, QMainWindow,
    QPushButton, QVBoxLayout, QListWidget, QListWidgetItem, QFormLayout,
    QHBoxLayout, QGridLayout,
    QLineEdit, QPlainTextEdit,
    QShortcut
)

import numpy as np
import platform
from datetime import datetime
from xml.dom import minidom
from utils import syntax
import os
from types import SimpleNamespace

from matplotlib.backends.qt_compat import QtCore, QtWidgets
if QtCore.qVersion() >= "5.":
    from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
else:
    from matplotlib.backends.backend_qt4agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure


        

class ScreenPenWindow(QMainWindow):
    def __init__(self, screen, screen_geom, pixmap: QtGui.QPixmap = None): # app: QApplication
        super().__init__()

        # PATHS
        try:
            prefix = sys._MEIPASS
        except Exception:
            prefix = os.path.abspath(".")

        self.files = SimpleNamespace(
            resources_xml = os.path.join(prefix, 'utils/resources.xml')
        )
                
        self.screen = screen
        self.screen_pixmap = pixmap
        self.screen_geom = screen_geom

        if platform.system() == 'Linux':
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.move(screen_geom.topLeft())
        self.setGeometry(screen_geom)
        self.activateWindow()
        self.showFullScreen()
        self._createCanvas()
        self._clearCanvas()
        
        self.history = self.drawingHistory(10)
        self.history.append(self.screen_pixmap)

        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()
        self.lastPoint = QtCore.QPoint()

        self.drawing = False
        self.curr_method = 'drawPath'
        self.curr_color = Qt.red
        self.curr_style = Qt.SolidLine
        self.curr_capstyle = Qt.RoundCap
        self.curr_joinstyle = Qt.RoundJoin
        self.curr_width = 3
        self.curr_br = QtGui.QBrush(self.curr_color)
        self.curr_pen = QtGui.QPen()
        self._setupTools()
        self._setupIcons()
        self._setupCodes()
        self._createToolBars()

        self.sc_undo = QShortcut(QKeySequence('Ctrl+Z'), self)
        self.sc_undo.activated.connect(self.undo)
        self.sc_redo = QShortcut(QKeySequence('Ctrl+Y'), self)
        self.sc_redo.activated.connect(self.redo)

    def _setCursor(self, cursor):
        if type(cursor) == str:
            pixm = QtGui.QPixmap.fromImage(QtGui.QImage.fromData(bytes(self._applySvgConfig(self._icons[cursor], None), encoding='utf-8')))
            pixm = pixm.scaled(QSize(32, 32))
            self.setCursor(QCursor(pixm, 2, 2))
        elif type(cursor) == Qt.CursorShape:
            self.setCursor(QCursor(cursor))

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        k = event.key()
        if (k==Qt.Key_Shift):
            self._setCursor('arrow2')

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        k = event.key()
        if (k==Qt.Key_Shift):
            self._setCursor(Qt.ArrowCursor)

    def _setupIcons(self):
        self._icons = {}
        try:
            DOMTree = minidom.parse(self.files.resources_xml)
            icons = DOMTree.getElementsByTagName('icon')
            if len(icons) < 1:
                raise Exception('ERROR: there are no icons in resources.xml file')
            for icon in icons:
                if icon.getAttribute('name')=='':
                    raise Exception('ERROR: resources.xml: icon doesnt contain "name" attribute')
                self._icons[icon.getAttribute('name')] = icon.getElementsByTagName('svg')[0].toxml().replace('\n', '')
        except FileNotFoundError as ex:
            print('ERROR: There is no resources.xml file')
            raise ex

    class Code(object): pass
    def _setupCodes(self):
        self._codes = []
        try:
            DOMTree = minidom.parse(self.files.resources_xml)
            codes = DOMTree.getElementsByTagName('code')
            if len(codes) < 1:
                raise Exception('ERROR: there are no codes in resources.xml file')
            for code in codes:
                if code.getAttribute('name')=='':
                    raise Exception('ERROR: resources.xml: code doesnt contain "name" attribute')
                codeobj = self.Code()
                codeobj.name = code.getAttribute('name')
                codeobj.label = code.getAttribute('name')
                codeobj.code = code.firstChild.data
                self._codes += [codeobj]
        except FileNotFoundError as ex:
            print('ERROR: There is no resources.xml file')
            raise ex


    def _applySvgConfig(self, svg_str, custom_colors_dict=None):
        colors_dict = {
            'STROKE': 'white',
            'FILL': 'silver'
        }
        if custom_colors_dict is not None:
            colors_dict = {**colors_dict, **custom_colors_dict}
        parsed = svg_str
        for el in colors_dict:
            parsed = parsed.replace(f'{{{el}}}', colors_dict[el])
        return parsed

    def _getIcon(self, name, custom_colors_dict=None):
        return QIcon(QtGui.QPixmap.fromImage(QtGui.QImage.fromData(bytes(self._applySvgConfig(self._icons[name], custom_colors_dict), encoding='utf-8'))))

    def _createCanvas(self):
        self.imageDraw = QtGui.QImage(self.size(), QtGui.QImage.Format_ARGB32)
        self.imageDraw_bck = QtGui.QImage(self.size(), QtGui.QImage.Format_ARGB32)
        

    def _clearCanvas(self):
        if platform.system() == 'Linux':
            self.imageDraw.fill(QtCore.Qt.transparent)
            self.imageDraw_bck.fill(QtCore.Qt.transparent)
            # self.imageDraw.fill(QtCore.Qt.white)
            # self.imageDraw_bck.fill(QtCore.Qt.white)
        else:
            qp = QtGui.QPainter(self.imageDraw)
            qp.drawPixmap(self.imageDraw.rect(), self.screen_pixmap, self.screen_pixmap.rect())
            qp.end()

            qp2 = QtGui.QPainter(self.imageDraw_bck)
            qp2.drawPixmap(self.imageDraw_bck.rect(), self.screen_pixmap, self.screen_pixmap.rect())
            qp2.end()
        self.update()

    def drawMatplotlib(self, qp:QtGui.QPainter, canvas:FigureCanvas, p1:QtCore.QPoint):
        size = canvas.size()
        width, height = size.width(), size.height()
        im = QtGui.QImage(canvas.buffer_rgba(), width, height, QtGui.QImage.Format_ARGB32).rgbSwapped()
        p2 = QtCore.QPoint(p1.x()+width, p1.y()+height) 
        qp.drawImage(QtCore.QRect(
            p1, 
            p2
        ), im, im.rect())

    def _setupTools(self):
        self.curr_br.setColor(self.curr_color)
        self.curr_pen.setStyle(self.curr_style)
        self.curr_pen.setCapStyle(self.curr_capstyle)
        self.curr_pen.setJoinStyle(self.curr_joinstyle)
        self.curr_pen.setBrush(self.curr_br)
        self.curr_pen.setWidth(self.curr_width)

    def setColor(self, color):
        def _setColor():
            self.curr_color = color
            self._setupTools()
        return _setColor

    def setStyle(self, style):
        def _setStyle():
            self.curr_style = style
            self._setupTools()
        return _setStyle

    def setWidth(self, width):
        def _setWidth():
            self.curr_width = width
            self._setupTools()
        return _setWidth

    def setAction(self, action):
        def _setAction():
            self.curr_method = action
        return _setAction

    class ChartDialog(QDialog):
        def ok_success(self, *args):
            sourcecode = '\n'.join(list(map(lambda x: f'    {x}', self.code.toPlainText().replace('\t', '').replace(' ', '').splitlines())))
            self.code = f'''
def drawChart(qp:QtGui.QPainter, p1:QtCore.QPoint):
{sourcecode}
    canvas = FigureCanvas(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    fwidth, fheight = fig.get_size_inches()
    fig_bbox = fig.get_window_extent(renderer)

    text_bbox = t.get_window_extent(renderer)

    tight_fwidth = text_bbox.width * fwidth / fig_bbox.width
    tight_fheight = text_bbox.height * fheight / fig_bbox.height

    fig.set_size_inches(tight_fwidth, tight_fheight)
    self.drawMatplotlib(qp, canvas, p1)
setattr(self, 'drawChart', drawChart)
'''
            exec(self.code, {'self': self.parent, **globals()})
            self.accept()

        def __init__(self, parent):
            super().__init__(parent=parent)
            self.parent = parent
            self.setWindowTitle("Chart")

            QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

            self.buttonBox = QDialogButtonBox(QBtn)
            self.buttonBox.accepted.connect(self.ok_success)
            self.buttonBox.rejected.connect(self.reject)
            
            self.resize(800, 600)
            self.code    = QPlainTextEdit()
            highlight = syntax.PythonHighlighter(self.code.document())
            self.code.zoomIn(4)
            self.code.setPlainText('')

            l = QListWidget()
            for c in self.parent._codes:
                ech = QListWidgetItem(c.label)
                ech.code = c.code
                ech.name = c.name
                l.addItem(ech)
            def code_clicked(c):
                self.code.setPlainText(c.code)
            l.itemClicked.connect(code_clicked)
            self.layout = QVBoxLayout()
            
            buttons = QHBoxLayout()
            buttons.addWidget(self.buttonBox, 1)

            codelay = QHBoxLayout()
            codelay.addWidget(l)
            codelay.addWidget(self.code, 1)

            self.layout.addLayout(codelay)
            self.layout.addLayout(buttons)

            self.setLayout(self.layout)

    def showChart(self):
        def _showChart():
            dlg = self.ChartDialog(self)
            if dlg.exec_():
                self.curr_method = 'drawChart'
            else:
                pass
        
        return _showChart

    def removeDrawing(self):
        def _removeDrawing():
            self._clearCanvas()
        return _removeDrawing

    def captureScreen(self):
        for tb in self.toolBars:
            tb.hide()
        img = self.imageDraw.copy()
        qp = QtGui.QPainter(img)
        qp.drawPixmap(img.rect(), self.screen_pixmap, self.screen_pixmap.rect())
        qp.drawImage(img.rect(), self.imageDraw, self.imageDraw.rect())
        qp.end()
        for tb in self.toolBars:
            tb.show()
        return img

    def saveDrawing(self):
        def _saveDrawing(n=0):
            filename = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            self.captureScreen().save(f'{filename}')
        return _saveDrawing

    def addAction(self, name, icon, fun):
        action = QAction(icon, name, self)
        action.triggered.connect(fun)
        return action


    def _createToolBars(self):
        penToolBar = QToolBar("Color", self)
        penToolBar.setIconSize(QSize(50, 50))
        actionBar = QToolBar("Action", self)
        actionBar.setIconSize(QSize(50, 50))
        self.toolBars = [penToolBar, actionBar]
        self.addToolBar(penToolBar)
        self.addToolBar(Qt.LeftToolBarArea, actionBar)
        
        avail_colors = {
            'red': Qt.red,
            'green': Qt.green,
            'blue': Qt.blue,
            'cyan': Qt.cyan,
            'magenta': Qt.magenta,
            'yellow': Qt.yellow,
            'black': Qt.black,
            'white': Qt.white,
            'orange': QColor('#ff8000'),
            'gray': QColor('#808080')
        }

        for acol in avail_colors:
            penToolBar.addAction(
                self.addAction(f'Set {acol} color', self._getIcon('rect_filled', {'FILL': acol, 'STROKE': 'none'}), self.setColor(avail_colors[acol]))
            )

        actionBar.addAction(self.addAction("Path", self._getIcon('path'), self.setAction('drawPath')))
        actionBar.addAction(self.addAction("Rect", self._getIcon('rect'), self.setAction('drawRect')))
        actionBar.addAction(self.addAction("Line", self._getIcon('line'), self.setAction('drawLine')))
        actionBar.addAction(self.addAction("Point", self._getIcon('dot'), self.setAction('drawDot')))
        actionBar.addAction(self.addAction("Matplotlib chart", self._getIcon('mpl'), self.showChart()))
        
        

        lineTypeMenu = QMenu()
        lineTypeMenu.addAction(self.addAction('Solid', self._getIcon('line'), self.setStyle(Qt.SolidLine)))
        lineTypeMenu.addAction(self.addAction('Dashed', self._getIcon('line_dashed'), self.setStyle(Qt.DashLine)))
        lineTypeButton = QToolButton(self)
        lineTypeButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        lineTypeButton.setIcon(self._getIcon('line_type'))
        lineTypeButton.setPopupMode(QToolButton.InstantPopup) # MenuButtonPopup
        lineTypeButton.setMenu(lineTypeMenu)
        lineTypeButton.setToolTip('Line type')
        actionBar.addWidget(lineTypeButton)

        lineWidthMenu = QMenu()
        lineWidthMenu.addAction(self.addAction('Thin', self._getIcon('line_thin'), self.setWidth(width=3)))
        lineWidthMenu.addAction(self.addAction('Medium', self._getIcon('line_medium'), self.setWidth(width=15)))
        lineWidthMenu.addAction(self.addAction('Thick', self._getIcon('line_thick'), self.setWidth(width=25)))
        lineWidthButton = QToolButton(self)
        lineWidthButton.setToolButtonStyle(Qt.ToolButtonIconOnly)
        lineWidthButton.setIcon(self._getIcon('line_width'))
        lineWidthButton.setPopupMode(QToolButton.InstantPopup)
        lineWidthButton.setMenu(lineWidthMenu)
        lineWidthButton.setToolTip('Line width')
        actionBar.addWidget(lineWidthButton)
        
        
        actionBar.addAction(self.addAction("Save image", self._getIcon('save'), self.saveDrawing())) # self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton)

        actionBar.addAction(self.addAction("Remove drawings", self._getIcon('remove'), self.removeDrawing()))
        

    def scaleCoords(self, coords):
        canvas_size = self.imageDraw.size()
        window_size = self.size()
        x_scale = canvas_size.width() / window_size.width()
        y_scale = canvas_size.height() / window_size.height()
        return QtCore.QPoint(coords.x()*x_scale, coords.y()*y_scale)

    def paintEvent(self, event):
        qp = QtGui.QPainter(self.imageDraw)
        canvasPainter = QtGui.QPainter(self)

        qp.setCompositionMode (QtGui.QPainter.CompositionMode_Source)
        canvasPainter.setCompositionMode (QtGui.QPainter.CompositionMode_Source)

        if Qt.LeftButton and self.drawing:
            qp.setPen(self.curr_pen)
            qp.setBrush(self.curr_br)
            if self.curr_method in ['drawRect']:
                qp.setBrush(Qt.NoBrush)
                self.curr_args = [QtCore.QRect(self.begin, self.end)]
                qp.drawImage(self.imageDraw.rect(), self.imageDraw_bck, self.imageDraw_bck.rect())
                
                getattr(qp, self.curr_method)(*self.curr_args)
                qp.setBrush(self.curr_br)
            elif self.curr_method in ['drawDot']:
                self.curr_args = [self.end, 10, 10]
                qp.drawImage(self.imageDraw.rect(), self.imageDraw_bck, self.imageDraw_bck.rect())
                
                getattr(qp, 'drawEllipse')(*self.curr_args)

            elif self.curr_method in ['drawLine']:
                qp.setBrush(Qt.NoBrush)
                self.curr_args = [self.begin, self.end]
                qp.drawImage(self.imageDraw.rect(), self.imageDraw_bck, self.imageDraw_bck.rect())
                
                getattr(qp, self.curr_method)(*self.curr_args)
                qp.setBrush(self.curr_br)

            elif self.curr_method in ['drawChart']:
                qp.drawImage(self.imageDraw.rect(), self.imageDraw_bck, self.imageDraw_bck.rect())
                try:
                    self.drawChart(qp, self.end)
                except Exception as ex:
                    self.drawing = False
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText(str(ex))
                    msgBox.exec()
                    
                    self.curr_method = 'drawPath'
                    self.update()
                    return


            elif self.curr_method in ['drawPath']:
                if self.lastPoint != self.end:
                    qp.setBrush(Qt.NoBrush)
                    qp.setPen(self.curr_pen)
                    self.path.cubicTo(self.end, self.end, self.end)
                    self.curr_args = [self.path]
                    getattr(qp, self.curr_method)(*self.curr_args)
                    self.lastPoint = self.end
                    self.update()
                    qp.setBrush(self.curr_br)

        qp.setCompositionMode (QtGui.QPainter.CompositionMode_SourceOver)
        qp.end()
        
        canvasPainter.drawImage(self.rect(), self.imageDraw, self.imageDraw.rect())
        canvasPainter.setCompositionMode (QtGui.QPainter.CompositionMode_SourceOver)
        canvasPainter.end()





    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            sys.exit(0)
            
        if event.button() == Qt.LeftButton and self.childAt(event.pos()) is None:
            self.drawing = True

        if self.curr_method in ['drawRect', 'drawChart', 'drawLine', 'drawDot']:
            qp = QtGui.QPainter(self.imageDraw_bck)
            qp.drawImage(self.imageDraw_bck.rect(), self.imageDraw, self.imageDraw.rect())
            qp.end()
            self.begin = self.scaleCoords(event.pos())
            self.end = self.scaleCoords(event.pos())
            
        elif self.curr_method in ['drawPath']:
            self.path = QtGui.QPainterPath()
            self.begin = self.scaleCoords(event.pos())
            self.end = self.scaleCoords(event.pos())
            self.path.moveTo(self.begin)
            self.lastPoint = self.scaleCoords(event.pos())
        self.update()

    def mouseMoveEvent(self, event):
        self.end = self.scaleCoords(event.pos())
        self.update()


    class drawingHistory(list):
        def __init__(self, limit=4):
            self.limit = limit
            self.current = -1
        
        def append(self, el):
            if self.current < len(self):
                del self[self.current + 1:]
                
            if len(self) >= self.limit:
                del self[0]
                self.current = self.limit - 2
            super().append(el)
            self.current += 1
            
        def extend(self, l):
            for el in l:
                self.append(el)
            
        def undo(self):
            if self.current > 0:
                self.current -= 1
            return self[self.current]
        
        def redo(self):
            if self.current + 1 < len(self):
                self.current += 1
            return self[self.current]
            
    def drawPixmap(self, p):
        qp = QtGui.QPainter(self.imageDraw)
        qp.setCompositionMode (QtGui.QPainter.CompositionMode_Source)
        qp.drawPixmap(self.imageDraw.rect(), p, p.rect())
        qp.end()

        qp2 = QtGui.QPainter(self.imageDraw_bck)
        qp2.setCompositionMode (QtGui.QPainter.CompositionMode_Source)
        qp2.drawPixmap(self.imageDraw_bck.rect(), p, p.rect())
        qp2.end()

    def undo(self):
        p = self.history.undo()
        self.drawPixmap(p)
        self.update()

    def redo(self):
        p = self.history.redo()
        self.drawPixmap(p)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing == True:
            self.drawing = False
            self.path = None

            self.begin = self.scaleCoords(event.pos())
            self.end = self.scaleCoords(event.pos())

            self.update()
            p = QPixmap()
            p.convertFromImage(self.imageDraw)
            self.history.append(p)

def _grab_screen(screen_idx, screen):
    screen_geom = QDesktopWidget().screenGeometry(screen_idx)
    return (
        screen_geom, 
        QScreen.grabWindow(
            screen, 
            QApplication.desktop().winId(), 
            screen_geom.x(), 
            screen_geom.y(), 
            screen.size().width(), 
            screen.size().height()
        )
    )
    

def _get_screens():
    screens = []
    for screen_idx, screen in enumerate(app.screens()):
        screen_geom, screen_pixmap = _grab_screen(screen_idx, screen)
        screens.append([screen, screen_geom, screen_pixmap])
    return screens

def show_screen_selection(screens):
    def _getScreenButton(pixmap, label):
        btn = QPushButton()
        ico = QIcon(pixmap)
        btn.setIcon(ico)
        btn.setIconSize(QSize(160, 160/(pixmap.rect().width()/pixmap.rect().height())))

        shad = QtWidgets.QGraphicsDropShadowEffect()
        shad.setOffset(-10, 10)
        shad.setColor(Qt.black)

        lay = QVBoxLayout(btn)
        lbl = QtWidgets.QLabel()
        lbl.setContentsMargins(0, 0, 0, 0)
        lbl.setStyleSheet("""color : white; font-weight:6000;""")
        lbl.setText(label)
        lbl.setGraphicsEffect(shad)
        lay.addWidget(lbl, alignment=QtCore.Qt.AlignCenter)
        return btn



    dlg = QDialog()
    dlg.layout = QGridLayout()
    dlg.layout.addWidget(QLabel('Select the screen') , 0, 0, 1, number_of_screens, alignment=QtCore.Qt.AlignCenter)

    def _getBtnAction(idx):
        def act():
            dlg.done(idx)
        return act

    for idx, scr in enumerate(screens):
        screen, screen_geom, screen_pixmap = scr
        label = f'Screen {idx+1}' if idx > 0 else f'Main screen'
        btn = _getScreenButton(screen_pixmap, label)
        btn.released.connect(_getBtnAction(idx+1))
        dlg.layout.addWidget(btn , 1, idx)
    dlg.setLayout(dlg.layout)
    return dlg.exec_()

def _setPalette(app):
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.black)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    app.setStyle("Fusion")

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-1', nargs='?', type=int, dest='screen', const='0')
    parser.add_argument('-2', nargs='?', type=int, dest='screen', const='1')
    parser.add_argument('-3', nargs='?', type=int, dest='screen', const='2')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    _setPalette(app)

    number_of_screens = len(app.screens())

    screens = _get_screens()
    
    if number_of_screens > 1 and args.screen is None:
        args.screen = show_screen_selection(screens)
        if args.screen == 0 or args.screen is None:
            print('No screen chosen, exiting.')
            sys.exit(0)
        else:
            args.screen -= 1

    screen, screen_geom, pixmap = screens[args.screen]
        
    window = ScreenPenWindow(screen, screen_geom, pixmap)
    sys.exit(app.exec_())
