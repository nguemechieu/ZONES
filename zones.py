import sys
import webbrowser

from PySide6.QtCore import Qt, Signal, QObject, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QColor, QPalette, QFont, QIcon, QPixmap
from PySide6.QtGui import QColor, QPalette, QFont
from PySide6.QtWidgets import QGraphicsOpacityEffect
from src.server.server_controller import  ServerController
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFrame
)

class AnimatedButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(45)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2D89EF;
                color: white;
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1B5FBD;
            }
            QPushButton:pressed {
                background-color: #144A94;
            }
            QPushButton:disabled {
                background-color: #7A7A7A;
            }
        """)

        # Press animation
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def mousePressEvent(self, event):
        rect = self.geometry()
        self.anim.stop()
        self.anim.setStartValue(rect)
        self.anim.setEndValue(QRect(rect.x(), rect.y() + 3, rect.width(), rect.height()))
        self.anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        rect = self.geometry()
        self.anim.stop()
        self.anim.setStartValue(rect)
        self.anim.setEndValue(QRect(rect.x(), rect.y() - 3, rect.width(), rect.height()))
        self.anim.start()
        super().mouseReleaseEvent(event)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.controller = ServerController()
        self.controller.server_stopped.connect(self.on_server_stopped)

        self.setWindowTitle("Zones")
        self.setMinimumSize(600, 500)

        # Background gradient
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#0F1C2E"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        # Fade-in animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(900)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()

        # Card container
        self.card = QFrame()
        self.card.setStyleSheet("""
            QFrame {
                background-color: #18293A;
                border-radius: 18px;
            }
        """)
        self.card.setFixedWidth(380)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(20)

        # Title
        self.label = QLabel("Welcome to Zones ")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        card_layout.addWidget(self.label)

        # Buttons
        self.start_btn = AnimatedButton("Start Zones")
        self.stop_btn = AnimatedButton("Stop Zones")
        self.stop_btn.setEnabled(False)

        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)

        card_layout.addWidget(self.start_btn)
        card_layout.addWidget(self.stop_btn)

        # Main layout
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.card, alignment=Qt.AlignCenter)
        layout.addStretch()

        # Slide-in animation for card
        self.card_anim = QPropertyAnimation(self.card, b"geometry")
        self.card_anim.setDuration(700)
        self.card_anim.setEasingCurve(QEasingCurve.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        rect = self.card.geometry()
        start_rect = QRect(rect.x(), rect.y() + 80, rect.width(), rect.height())
        self.card_anim.setStartValue(start_rect)
        self.card_anim.setEndValue(rect)
        self.card_anim.start()

    def start_server(self):
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.animate_label("Zones is running...", "#2DFF88")
        self.controller.start_server()

    def stop_server(self):
        self.animate_label("Stopping server...", "#FFB347")
        self.controller.stop_server()

    def on_server_stopped(self):
        self.animate_label("Server stopped", "#FF6B6B")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.close()

    def animate_label(self, text, color):
        self.label.setText(text)
        self.label.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")

        # Fade animation
        effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(600)
        anim.setStartValue(0.2)
        anim.setEndValue(1)
        anim.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("Zones")
    window.setWindowIcon(QIcon("src/assets/Zones.ico"))
    logo_image = QLabel()
    logo_image.setPixmap(QPixmap("src/assets/logo.png"))
    logo_image.setAutoFillBackground( True)

    logo_image.setStyleSheet("""
    QLabel {
    color: white;
    font-size: 20px;
    font-weight: bold;
    background-color: transparent;
    background-image: url("src/assets/Zones.png");
    
    }
    """)
    window.layout().addWidget(logo_image)
    window.show()

    window.show()
    sys.exit(app.exec())
