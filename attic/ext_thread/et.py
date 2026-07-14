#!/usr/bin/env python

#from fbs_runtime.application_context.PyQt5 import ApplicationContext  NOT WORKING

from PyQt5.QtCore import QDateTime, Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit,
                             QDial, QDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
        QProgressBar, QPushButton, QRadioButton, QScrollBar, QSizePolicy,
        QSlider, QSpinBox, QStyleFactory, QTableWidget, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget)
from PyQt5.QtGui import QIntValidator, QDoubleValidator, QFont
from PyQt5 import QtSvg
import sys

class ext_thrd_ui(QDialog):
    def __init__(self, parent=None):
        super( ext_thrd_ui, self).__init__(parent)
        self.originalPalette = QApplication.palette()
        self.setFont( QFont("Arial",16) )
        #self.setFont( QFont("Helvetica",16) )
        
        unitComboBox = QComboBox()
        unitComboBox.addItems(["inch", " mm "])

        caComboBox = QComboBox()
        caComboBox.addItems(["0", "29.5"])

        caLabel = QLabel("Compound Angle")
        caLabel.setBuddy(caComboBox)

        self.createSvgIcon();
        self.createRightGroupBox()
        
        topLayout = QHBoxLayout()
        topLayout.addWidget(unitComboBox)
        topLayout.addStretch(1)
        topLayout.addWidget(caLabel)
        topLayout.addWidget(caComboBox)

        mainLayout = QGridLayout()
        mainLayout.addLayout(topLayout, 0, 0, 1, 2)  # row, col, row span, col span
        mainLayout.addWidget(self.sw, 1, 0)
        mainLayout.addWidget(self.rightGroupBox, 1, 1)
        
        self.setLayout(mainLayout)
        self.setWindowTitle("Ext Thread")

    def createRightGroupBox(self):
        self.rightGroupBox = QGroupBox()

        #self.rightGroupBox.setFlat(True)  #no effect ?
        #self.rightGroupBox.setStyleSheet("QGroupBox#rightGroupBox {border:0;}")  # change font size ?
        #self.rightGroupBox.setStyleSheet("border:0;")

        cutLength = QLineEdit()
        cutLength.setValidator(QDoubleValidator(0.01,99.99,2))
        cutLength.setAlignment(Qt.AlignRight)
        cutLength.setPlaceholderText( "0.250" )
                
        pitch = QLineEdit()    # pitch in mm has one decimal digit, but tpi is integer
        pitch.setValidator(QIntValidator())
        pitch.setMaxLength(4)
        pitch.setAlignment(Qt.AlignRight)
        pitch.setPlaceholderText( "28" )  # light color

        self.GB = QGroupBox("GroupBox")
        groupBox1 = QGroupBox("Z (lathe bed/leadscrew)")
        #groupBox1.setObjectName("LengthGB")
                
        layout1 = QFormLayout()
        layout1.addRow("Length", cutLength )
        layout1.addRow("Pitch",  pitch)
        groupBox1.setLayout(layout1)

        self.createDepthGroup()

        runPushButton = QPushButton("Run")
        runPushButton.setCheckable(True)
        runPushButton.setChecked(True)

        layout = QVBoxLayout()
        layout.addWidget(groupBox1)
        layout.addStretch(1)
        layout.addWidget(self.depthGroupBox)
        layout.addStretch(1)
        layout.addWidget(runPushButton)

        self.rightGroupBox.setLayout(layout)

    def createDepthGroup(self):
        self.depthGroupBox = QGroupBox("X (cross-slide)")

        totalCutDepth = QLineEdit()
        totalCutDepth.setValidator(QDoubleValidator(0.001, 9.99, 3))
        totalCutDepth.setAlignment(Qt.AlignRight)
        totalCutDepth.setPlaceholderText( "0.020" )

        firstCutDepth = QLineEdit()
        firstCutDepth.setValidator(QDoubleValidator(0.001, 9.99, 3))
        firstCutDepth.setAlignment(Qt.AlignRight)
        firstCutDepth.setPlaceholderText( "0.000" )

        cutDepthPPass = QLineEdit()
        cutDepthPPass.setValidator(QDoubleValidator(0.001, 9.99, 3))
        cutDepthPPass.setAlignment(Qt.AlignRight)
        cutDepthPPass.setPlaceholderText( "0.002" )

        layout = QFormLayout()
        layout.addRow("Depth total",  totalCutDepth)
        layout.addRow("first pass",  firstCutDepth)
        layout.addRow("depth/pass",  cutDepthPPass)
        
        self.depthGroupBox.setLayout(layout)

    def createSvgIcon(self):
        self.sw = QtSvg.QSvgWidget('ext_thread2_dim.svg')
        self.sw.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
        self.sw.setStyleSheet("background-color:grey;");

if __name__ == '__main__':
    app = QApplication([])
    etui = ext_thrd_ui()
    #etui.setFixedWidth(800)
    #etui.setFixedHeight(480)
    etui.show()
    app.exec()
