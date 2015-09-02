#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
''' HMI de controlador de báscula de flujo basado en dsPIC v1.0
    Cliente: Agripac - Planta San Camilo
    Diseñado y construido por: Joao Desiderio, DesiCO. c.2015
'''
import sys
import sqlite3 as lite
import datetime, time
import os.path
import serial
from PyQt4.QtGui import * # QApplication, QMainWindow, QTextCursor
from PyQt4.QtCore import QObject, SIGNAL, QThread, Qt
from PyQt4 import uic
import socket  # for sockets

base, form = uic.loadUiType("/home/workspace/Balanza/ui/balanzaHMI.ui")

class CMainWindow(base, form):
    def __init__(self, parent = None):
        super(base, self).__init__(parent)
        self.setupUi(self)

        self.ser = None
        self.sc = None
        self.reader = CReader()
        self.writer = CWriter()

        self.print_info("Master, I'm Ready...")

        QObject.connect(self.btnStart, SIGNAL("clicked()"), self.start_cmd)
        QObject.connect(self.btnStop, SIGNAL("clicked()"), self.stop_cmd)
        QObject.connect(self.btnZero, SIGNAL("clicked()"), self.zero_cmd)
        QObject.connect(self.btnSetup, SIGNAL("clicked()"), self.setup_cmd)

        QObject.connect(self.reader, SIGNAL("newData(QString)"), self.update_screen)
        QObject.connect(self.reader, SIGNAL("error(QString)"), self.print_error)
        QObject.connect(self.writer, SIGNAL("error(QString)"), self.print_error)


    def connectToHost(self, **kwargs):	# create an INET, STREAMing socket
        try:
            self.sc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if __debug__:
                host_IP = '192.168.1.98'
            else:
                host_IP = '192.168.1.7'

            self.sc.connect((host_IP, 1809))
            print 'conectado a ' + host_IP
            assert isinstance(self.sc, object)

        except socket.error:
            print 'Failed to create socket'


    def connect(self, **kwargs):
        self.disconnect()

        try:
            # self.print_info("Connecting to %s with %s baud rate." % (self.getSelectedPort(), self.getSelectedBaudRate()))
            self.ser = serial.Serial('/dev/ttyO1', 115200)
            # self.ser = serial.Serial('/dev/ttyUSB0', 115200)
            self.start_reader(self.ser)
            self.print_info("Connected successfully.")
            self.writer.start(self.ser, "Ready...\r")
        except:
            self.ser = None
            self.print_error("Failed to connect!")

    def disconnect(self, **kwargs):
        self.stop_threads()
        if self.ser is None:
            return
        try:
            if self.ser.isOpen:
                self.ser.close()
                self.print_info("Disconnected successfully.")
        except:
            self.print_error("Failed to disconnect!")
        self.ser = None

    def start_reader(self, ser):
        self.reader.start(ser)

    def stop_threads(self):
        self.stop_reader()
        self.stop_writer()

    def stop_reader(self):
        if self.reader.isRunning():
            self.reader.terminate()

    def stop_writer(self):
        if self.writer.isRunning():
            self.writer.terminate()


    @staticmethod
    def print_info(text):
        print(text)

    def print_error(self, text):
        print(text)

    def print_cmd(self, text):
        print("> " + text + "\n\n")

    def update_screen(self, text):
        s = text.split(",")

        global numero_de_acumulaciones_registrado,\
            factorDeCorreccion, \
            peso_acumulado, \
            numero_de_orden

        if len(s) == 8:
            numero_de_acumulaciones = format(int(s[1]), '8,d')
            peso_actual = float(s[2])
            peso_capturado = float(s[3])
            hora = time.strftime("%H:%M:%S")

            inputs = s[5].toUShort(16)[0]  # devuelve una tupla (int, bool)
            outputs = s[6].toUShort(16)[0]
            status = s[7].toUShort(16)[0]

            fill = outputs & 0x01
            dump = outputs & 0x02
            motion = status & 0x01
            zero = status & 0x20

            if fill:
                self.lblProcessStatus.setText('Filling')
                self.frmTolvaAlimentadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaAlimentadoraAbierta.gif);")
                self.frmTolvaPesadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaPesadoraCerrada.gif);")

            elif dump:
                self.lblProcessStatus.setText('Dumping')
                self.frmTolvaAlimentadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaAlimentadoraCerrada.gif);")
                self.frmTolvaPesadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaPesadoraAbierta.gif);")
            else:
                self.lblProcessStatus.setText('  ')
                self.frmTolvaAlimentadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaAlimentadoraCerrada.gif);")
                self.frmTolvaPesadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaPesadoraCerrada.gif);")

            if motion:
                self.lblScaleStatus.setText('Motion')
            elif zero:
                self.lblScaleStatus.setText('->0<-')
            else:
                self.lblScaleStatus.setText('kg')

            if (-2 < peso_actual < 2) and zero:
                factorDeCorreccion = peso_actual
                peso_actual = 0
                print factorDeCorreccion
            else:
                peso_actual -= factorDeCorreccion

            self.lblPeso.setText(format(peso_actual, '.2f'))

            if numero_de_acumulaciones != numero_de_acumulaciones_registrado:
                peso_acumulado += peso_capturado
                record_date = datetime.datetime.now()
                self.lblNumAcum.setText(numero_de_acumulaciones)
                self.lblUltimaCaptura.setText(format(peso_capturado, '.2f') + ' kg')
                self.lblAcumulado.setText(format(peso_acumulado, '8,.2f') + ' kg')
                self.lblHoraCaptura.setText(hora)

                data = {
                    'record_date': record_date,
                    'numero': numero_de_acumulaciones,
                    'peso': peso_actual,
                    'acumulado': peso_acumulado,
                    'orden': numero_de_orden
                }

                save_registro(data)

                dato = str('11;' + s[1] + ';' + s[2] + ';' + format(peso_acumulado, '8.2f') + ';' + format(numero_de_orden) + ';' + record_date.strftime('%Y-%m-%d;%H:%M:%S') + "\n")
                # z = (dato)
                # print dato, len(dato), type(dato), z
                self.sc.sendall(dato)

                numero_de_acumulaciones_registrado = numero_de_acumulaciones

        else:
            self.logPlainTextEdit.moveCursor(QTextCursor.End)
            self.logPlainTextEdit.insertPlainText(text)

    def process_cmd(self):
        cmd = self.cmdLineEdit.text().toUpper() + "\r"
        self.writer.start(self.ser, cmd)
        self.cmdLineEdit.clear()


    def start_cmd(self):

        mainWindow.btnStart.setStyleSheet("border-image: url(/home/workspace/Balanza/ui/botonGris.gif);\n"
                                          "border-color: rgb(255, 255, 255);\n"
                                          "color: rgb(255, 255, 255);")
        mainWindow.btnStop.setStyleSheet("border-image: url(/home/workspace/Balanza/ui/botonRojo.gif);\n"
                                          "border-color: rgb(255, 255, 255);\n"
                                          "color: rgb(255, 255, 255);")
        #mainWindow.frmTolvaAlimentadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaAlimentadoraAbierta.gif);")
        #mainWindow.frmTolvaPesadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaPesadoraAbierta.gif);")

        mainWindow.btnStart.setEnabled(False)
        mainWindow.btnStop.setEnabled(True)
        self.writer.start(self.ser, "R\r")


    def stop_cmd(self):
        mainWindow.btnStart.setStyleSheet("border-image: url(/home/workspace/Balanza/ui/BotonVerde.gif);\n"
                                          "border-color: rgb(255, 255, 255);\n"
                                          "color: rgb(255, 255, 255);")
        mainWindow.btnStop.setStyleSheet("border-image: url(/home/workspace/Balanza/ui/botonGris.gif);\n"
                                          "border-color: rgb(255, 255, 255);\n"
                                          "color: rgb(255, 255, 255);")

        #mainWindow.frmTolvaAlimentadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaAlimentadoraCerrada.gif);")
        #mainWindow.frmTolvaPesadora.setStyleSheet("image: url(/home/workspace/Balanza/ui/tolvaPesadoraCerrada.gif);")

        mainWindow.btnStart.setEnabled(True)
        mainWindow.btnStop.setEnabled(False)
        self.writer.start(self.ser, "P\r")
        print "Parando"


    def zero_cmd(self):
        self.writer.start(self.ser, "Z\r")


    def setup_cmd(self):
        if mainWindow.sW.currentWidget() == self.pgDatos:
            mainWindow.sW.setCurrentWidget(self.pgAjuste)
            print 'ajuste'
        else:
            mainWindow.sW.setCurrentWidget(self.pgDatos)
            print 'datos'

        self.writer.start(self.ser, "S\r")


    def closeEvent(self, event):
        # self.pgAjuste.cmdLineEdit.setText('P')
        self.process_cmd()
        self.disconnect()
        # CMainWindow.sc.close()


class CReader(QThread):
    def start(self, ser, priority=QThread.InheritPriority):
        self.ser = ser
        QThread.start(self, priority)

    def run(self):
        while True:
            try:
                data = self.ser.read(1)
                # n = self.ser.inWaiting()
                # if n:
                # 	data += self.ser.read(n)
                if len(data) == 0:
                    break

                c = data
                global serial_buffer
                # check if character is a delimeter

                if c == '\n':
                    c = ''  # don't want returns. chuck it

                if chr(27) in c:
                    c = ''

                if c == '\r':
                    serial_buffer += "\n"  # add the newline to the buffer
                    self.emit(SIGNAL("newData(QString)"), serial_buffer)
                    serial_buffer = ''
                else:
                    serial_buffer += c

            except:
                errMsg = "Reader thread is terminated unexpectedly."
                self.emit(SIGNAL("error(QString)"), errMsg)
                break


class CWriter(QThread):
    def start(self, ser, cmd="", priority=QThread.InheritPriority):
        self.ser = ser
        self.cmd = cmd
        QThread.start(self, priority)

    def run(self):
        try:
            self.ser.write(str(self.cmd))
        except:
            errMsg = "Writer thread is terminated unexpectedly."
            self.emit(SIGNAL("error(QString)"), errMsg)

    def terminate(self):
        self.wait()
        QThread.terminate(self)


def save_registro(data):
    """
    Manda a guardar los datos localmente.

    :return:
    """

    # print 'Guardando registro localmente..'
    try:
        if __debug__:
            con = lite.connect('/home/workspace/registro.db')
        else:
            con = lite.connect('/media/DATALOG/registro.db')

        cur = con.cursor()
        sql = 'INSERT INTO registro VALUES(' \
              '"{record_date}",' \
              '"{numero}",' \
              '"{peso}",' \
              '"{acumulado}",' \
              '"{orden}"' \
              ');'.format(**data)

        cur.execute(sql)

    except lite.Error as e:
        # logger.error("Error %s:" % str(e) + "\n Base local: Intentando crear la tabla..")
        if cur:
            cur.execute("CREATE TABLE IF NOT EXISTS "
                        "registro("
                        "record_date DATETIME, "
                        "number TEXT, "
                        "peso TEXT, "
                        "acumulado TEXT, "
                        "orden INT"
                        ");")
            # logger.error("Intentando grabar datos localmente por segunda vez..")
            cur.execute(sql)

    finally:
        if con:
            con.commit()
            con.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # make our own buffer
    # useful for parsing commands
    # Serial.readline seems unreliable at times too
    serial_buffer = ""
    peso_acumulado = 0
    numero_de_acumulaciones_registrado = 0
    factorDeCorreccion = 0

    if __debug__:
        sPath = '/home/workspace/registro.db'
    else:
        sPath = '/media/DATALOG/registro.db'

    if os.path.isfile(sPath):
        conn = lite.connect(sPath).cursor()
        conn.execute('SELECT acumulado, orden FROM registro ORDER BY record_date DESC LIMIT 1')
        all_rows = conn.fetchall()

        peso_acumulado = float(all_rows[0][0])
        numero_de_orden = int(all_rows [0][1]) + 1

    mainWindow = CMainWindow()  # constructor
    mainWindow.connect()    # conecta al puerto serial
    mainWindow.connectToHost()  #conecta al servidor remoto
    mainWindow.lblAcumulado.setText(format(peso_acumulado, '8,.2f') + ' kg')
    icon = QIcon()
    icon.addPixmap(QPixmap("/home/workspace/Balanza/ui/DySCR.ico"), QIcon.Normal, QIcon.Off)

    mainWindow.setWindowIcon(icon)
    mainWindow.show()
    mainWindow.setWindowState(Qt.WindowMaximized)

    sys.exit(app.exec_())