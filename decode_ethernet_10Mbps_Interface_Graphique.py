"""
Programme pédagogique pour le décodage Ethernet de signaux Manchester à partir de fichiers CSV
-----------------------------------------------------------------------------------------------

Ce programme est conçu pour illustrer le processus de décodage de signaux Ethernet codés en Manchester, 
ainsi que la structure de la trame Ethernet, en utilisant des données recueillies par des oscilloscopes. 
Les données sont chargées à partir de fichiers CSV produits par différents modèles d'oscilloscopes 
(Tektronix MSO, Rigol, Tektronix TDS2012). Le programme supporte les formats de sortie spécifiques à chaque 
modèle d'oscilloscope et propose une interface utilisateur pour visualiser et interpréter les trames Ethernet.
La démarche utilisée pour arriver à traiter les trames Ethernet est expliquée dans l'article: "Ethernet à la loupe: 
de la couche physique au décodage des trames" publié dans le magazine Hackable, n°61 juillet/août 2025, Editions Diamond.

Fonctionnalités :
- Traitement et filtrage du signal reçu : suppression d'un éventuel décalage vertical et alignement du début du signal.
- Décodage des données avec le schéma de codage Manchester, prenant en charge un débit de 10 Mbps.
- Extraction des éléments de la trame Ethernet (préambule, adresses de destination et source, type et données).
- Affichage interactif de chaque section de la trame Ethernet avec des annotations graphiques (préambule, 
  adresse de destination, adresse source, type, et données).
  

Contact:
Thomas LAVARENNE
thomas.lavarenne@ac-creteil.fr


Licence :
Ce programme est distribué sous la licence Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International 
(CC BY-NC-ND 4.0). Vous êtes libre de partager ce programme dans un cadre non commercial et privé, 
mais vous ne pouvez pas le modifier ni le redistribuer sans autorisation. Aucune utilisation commerciale ou diffusion publique 
n'est autorisée. Pour plus d'informations : https://creativecommons.org/licenses/by-nc-nd/4.0/
"""

import sys
import csv
import numpy as np
from PyQt5 import QtWidgets
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QFileDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QLabel, QPushButton, QComboBox
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Classe pour charger les données CSV en fonction du modèle d'oscilloscope
class ChargeurCSV:
    def __init__(self, chemin_fichier, modele):
        self.chemin_fichier = chemin_fichier
        self.intervalle_echantillon = None
        self.donnees = []
        self.modele = modele

    def charger_donnees(self):
        if self.modele == "Tektronix MSO":
            self._charger_donnees_tektronix_mso()
        elif self.modele == "Rigol":
            self._charger_donnees_rigol()
        elif self.modele == "Tektronix TDS2012":
            self._charger_donnees_tektronix_tds2012()
        return np.array(self.donnees), self.intervalle_echantillon

    def _charger_donnees_tektronix_mso(self):
        with open(self.chemin_fichier, 'rt') as f:
            lecteur = csv.reader(f)
            for index, ligne in enumerate(lecteur):
                if len(ligne) == 0:
                    continue
                if ligne[0] == 'Sample Interval':
                    self.intervalle_echantillon = float(ligne[1].replace(",", "."))
                if index > 17:
                    self.donnees.append(float(ligne[1]))

    def _charger_donnees_rigol(self):
        with open(self.chemin_fichier, 'rt') as f:
            lecteur = csv.reader(f)
            for index, ligne in enumerate(lecteur):
                if len(ligne) == 0:
                    continue
                if ligne[0] == 'Sampling Period':
                    self.intervalle_echantillon = float(ligne[1].replace(",", "."))
                if index > 26:
                    self.donnees.append(float(ligne[0]))

    def _charger_donnees_tektronix_tds2012(self):
        with open(self.chemin_fichier, 'rt') as f:
            lecteur = csv.reader(f)
            for index, ligne in enumerate(lecteur):
                if len(ligne) == 0:
                    continue
                if ligne[0] == 'Sample Interval':
                    self.intervalle_echantillon = float(ligne[1].replace(",", "."))
                if index > 0:
                    self.donnees.append(float(ligne[4]))


class TraitementSignal:
    def __init__(self, donnees, intervalle_echantillon):
        self.donnees = donnees
        self.intervalle_echantillon = intervalle_echantillon

    def supprimer_composante_continue(self):
        self.donnees = self.donnees - np.mean(self.donnees)
        self.donnees = self.donnees / max(self.donnees)

    def aligner_debut_signal(self):
        index = 0
        while self.donnees[index] < 0.15:
            index += 1
        self.donnees = self.donnees[index:]

    def obtenir_donnees_traitees(self):
        return self.donnees


class DecodeurManchester:
    def __init__(self, donnees, intervalle_echantillon, debit=10e6):
        self.donnees = donnees
        self.intervalle_echantillon = intervalle_echantillon
        self.debit = debit
        self.nbr_ech_bit = int(round(1 / (self.intervalle_echantillon * self.debit)))
        self.decode = ''

    def decoder_donnees(self):
        i = self.nbr_ech_bit // 4
        while i < len(self.donnees) - self.nbr_ech_bit // 2:
            if self.donnees[i] > 0 and self.donnees[i + self.nbr_ech_bit // 2] < 0:
                self.decode += '1'
            elif self.donnees[i] < 0 and self.donnees[i + self.nbr_ech_bit // 2] > 0:
                self.decode += '0'
            i += self.nbr_ech_bit
        self.preambule_corr = False #PROBLEME: IL MANQUE '10' POUR CERTAINS PREAMBULES??
        if self.decode[:64] != '1010101010101010101010101010101010101010101010101010101010101011':
            self.decode = '10' + self.decode
            self.preambule_corr = True
            print("Ajout '10' manquant dans le preambule")
        return self.decode


class ExtracteurTrame:
    def __init__(self, donnees_binaires):
        self.donnees_binaires = donnees_binaires
        self.donnees_hex = ''

    def extraire_octets(self):
        self.donnees_hex = ''
        i = 0
        while i < len(self.donnees_binaires) - 8:
            octet = self.donnees_binaires[i:i + 8][::-1]
            self.donnees_hex += hex(int(octet, 2))[2:].zfill(2) + ' '
            i += 8
        return self.donnees_hex

    def obtenir_adresses(self):
        preambule = self.donnees_hex[:8*3]
        destination = self.donnees_hex[8*3:8*3+6 * 3]
        source = self.donnees_hex[8*3+6 * 3:8*3+6 * 3 + 6 * 3]
        ethertype = self.donnees_hex[8*3+6 * 3 + 6 * 3:8*3+6 * 3 + 6 * 3 + 2 * 3]
        return preambule, destination, source, ethertype, self.donnees_hex[8*3+6 * 3 + 6 * 3 + 2 * 3:]


# Interface graphique principale

class Interface(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.donnees = None
        self.intervalle_echantillon = None
        self.processed_data = None
        self.decodeur = None
        self.extracteur = None
        self.modele = "Tektronix MSO"
        self.debit = 10e6
        self.decode_display = {'destination': False, 'source': False, 'type': False, 'data': False}

    def initUI(self):
        # Layout principal
        layout = QVBoxLayout()

        # Graphique pour la trame complète
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(self.canvas)
        self.ax = self.canvas.figure.subplots()

        # Graphique pour le préambule, les adresses MAC et le type
        self.canvas2 = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(self.canvas2)
        self.ax2 = self.canvas2.figure.subplots()

        # Sélecteur de modèle d'oscilloscope
        self.modele_label = QLabel("Modèle d'oscilloscope :")
        self.modele_label.setStyleSheet("font-size: 18px;")
        self.modele_label.setFont(QFont("Arial", weight=QFont.Bold))
        layout.addWidget(self.modele_label)

        self.modele_selector = QComboBox()
        self.modele_selector.addItems(["Tektronix MSO", "Rigol", "Tektronix TDS2012"])
        self.modele_selector.setStyleSheet("font-size: 18px;")
        self.modele_selector.currentIndexChanged.connect(self.selectionner_modele)
        layout.addWidget(self.modele_selector)

        # Bouton pour charger le fichier CSV
        btn_load = QPushButton("Charger CSV")
        btn_load.setStyleSheet("font-size: 18px;")
        btn_load.clicked.connect(self.charger_csv)
        layout.addWidget(btn_load)

        # Ligne pour Sample Interval
        ligne_sample_interval = QHBoxLayout()
        self.sample_interval_label = QLabel("Sample Interval : N/A")
        self.sample_interval_label.setStyleSheet("font-size: 18px;")
        self.sample_interval_label.setFont(QFont("Arial", weight=QFont.Bold))
        ligne_sample_interval.addWidget(self.sample_interval_label)
        layout.addLayout(ligne_sample_interval)

        self.debit_label = QLabel("Débit binaire : 10 Mbps")
        self.debit_label.setStyleSheet("font-size: 18px;")
        self.debit_label.setFont(QFont("Arial", weight=QFont.Bold))
        ligne_sample_interval.addWidget(self.debit_label)
        layout.addLayout(ligne_sample_interval)

        self.nbr_ech_label = QLabel("Nombre ech/bit : N/A")
        self.nbr_ech_label.setStyleSheet("font-size: 18px;")
        self.nbr_ech_label.setFont(QFont("Arial", weight=QFont.Bold))
        ligne_sample_interval.addWidget(self.nbr_ech_label)
        layout.addLayout(ligne_sample_interval)



        # Informations sur le décodage (Destination, Source, Type, Data)
        self.create_info_section(layout)

        # Finaliser le layout
        self.setLayout(layout)

    def create_info_section(self, layout):
        # Destination et Source sur la même ligne
        ligne_dest_src = QHBoxLayout()
        
        # PRE: affiche/supprime
        self.radio_pre_afficher = QRadioButton("Afficher PRE+SFD")
        self.radio_pre_afficher.setStyleSheet("font-size: 18px;")
        self.radio_pre_afficher.toggled.connect(self.update_decode)
        ligne_dest_src.addWidget(self.radio_pre_afficher)
        self.info_label_pre = QLabel("Type : N/A")
        ligne_dest_src.addWidget(self.info_label_pre)
        
        # Destination: affiche/supprime
        self.radio_dest_afficher = QRadioButton("Afficher DESTINATION")
        self.radio_dest_afficher.setStyleSheet("font-size: 18px;")  # Augmente la taille de la police
        self.radio_dest_afficher.toggled.connect(self.update_decode)
        ligne_dest_src.addWidget(self.radio_dest_afficher)
        self.info_label_dest = QLabel("Destination : N/A")
        ligne_dest_src.addWidget(self.info_label_dest)

        # Source: affiche/supprime
        self.radio_src_afficher = QRadioButton("Afficher SOURCE")
        self.radio_src_afficher.setStyleSheet("font-size: 18px;")
        self.radio_src_afficher.toggled.connect(self.update_decode)
        ligne_dest_src.addWidget(self.radio_src_afficher)
        self.info_label_src = QLabel("Source : N/A")
        ligne_dest_src.addWidget(self.info_label_src)

        # Type: affiche/supprime
        self.radio_type_afficher = QRadioButton("Afficher TYPE")
        self.radio_type_afficher.setStyleSheet("font-size: 18px;")
        self.radio_type_afficher.toggled.connect(self.update_decode)
        ligne_dest_src.addWidget(self.radio_type_afficher)
        self.info_label_type = QLabel("Type : N/A")
        ligne_dest_src.addWidget(self.info_label_type)

        layout.addLayout(ligne_dest_src)

        # Data: affiche/supprime
        self.radio_data_afficher = QRadioButton("Afficher DATA")
        self.radio_data_afficher.setStyleSheet("font-size: 18px;")
        self.radio_data_afficher.toggled.connect(self.update_decode)
        layout.addWidget(self.radio_data_afficher)
        self.info_label_data = QLabel("Data : N/A")
        layout.addWidget(self.info_label_data)

    def selectionner_modele(self, index):
        self.modele = self.modele_selector.currentText()

    def reset_fields(self):
        # Remet tous les labels et champs à "N/A" et désélectionne les boutons radio
        self.sample_interval_label.setText("Sample Interval : N/A")
        self.info_label_pre.setText("PRE+SFD : N/A")
        self.info_label_dest.setText("Destination : N/A")
        self.info_label_src.setText("Source : N/A")
        self.info_label_type.setText("Type : N/A")
        self.info_label_data.setText("Data : N/A")

        # Désélectionner les boutons radio
        self.radio_pre_afficher.setChecked(False)
        self.radio_dest_afficher.setChecked(False)
        self.radio_src_afficher.setChecked(False)
        self.radio_type_afficher.setChecked(False)
        self.radio_data_afficher.setChecked(False)

        # Effacer les tracés des graphiques
        self.ax.clear()
        self.ax2.clear()
        self.canvas.draw()
        self.canvas2.draw()

    def charger_csv(self):
        self.reset_fields()
        chemin_fichier, _ = QFileDialog.getOpenFileName(self, "Charger un fichier CSV", "", "CSV Files (*.csv)")
        if chemin_fichier:
            chargeur = ChargeurCSV(chemin_fichier, self.modele)
            self.donnees, self.intervalle_echantillon = chargeur.charger_donnees()

            processeur = TraitementSignal(self.donnees, self.intervalle_echantillon)
            processeur.supprimer_composante_continue()
            processeur.aligner_debut_signal()
            self.processed_data = processeur.obtenir_donnees_traitees()
           

            self.decodeur = DecodeurManchester(self.processed_data, self.intervalle_echantillon, self.debit)
            donnees_decodees = self.decodeur.decoder_donnees()

            self.extracteur = ExtracteurTrame(donnees_decodees)
            self.extracteur.extraire_octets()

            # Mise à jour des labels
            self.sample_interval_label.setText(f"Sample Interval : {self.intervalle_echantillon:.2e} s")
            self.nbr_ech_label.setText(f"Nombre ech/bit: : {self.decodeur.nbr_ech_bit}")

            # Affichage des graphiques
            self.ax.clear()
            self.ax.set_ylim(-1.5,1.5)
            self.canvas.draw()

            # Graphique pour les data
            self.ax2.clear()
            data_for_type = self.processed_data[:]  # Calcul ajusté pour les adresses et type
            self.ax2.plot(data_for_type)
            self.ax2.set_title("Trame complète")
            self.ax2.set_ylim(-1.5,1.5)
            self.canvas2.draw()
    def update_decode(self):
        # Réinitialisation des axes avant de redessiner les graphiques
        self.ax.clear()
        self.ax2.clear()

    # Gérer l'affichage ou la suppression des informations en fonction des boutons sélectionnés
        corr = 0
        if self.decodeur.preambule_corr == True:
            corr = 2*self.decodeur.nbr_ech_bit

        if self.radio_pre_afficher.isChecked():
            preambule, _ , _, _, _ = self.extracteur.obtenir_adresses()
            self.extracted_data = self.processed_data[:-corr + 8*8*self.decodeur.nbr_ech_bit]
            couleur = 'grey'
            label = preambule
            label2 =''
            if self.decodeur.preambule_corr == True:
                labelb=self.decodeur.decode[2:8*8]
            else:
                labelb=self.decodeur.decode[:8*8]
            self.info_label_pre.setText(f"PRE+SFD : {preambule}")
            self.info_label_pre.setStyleSheet("font-size: 22px; color: grey;")
        # Tracer le rectangle de pre
            self.ax2.text(0, 1.25, 'Preambule+SFD', color='grey', fontsize=14)
            self.ax2.add_patch(plt.Rectangle((0, -1.1),-corr+ self.decodeur.nbr_ech_bit * (8 * 8), 2.2, edgecolor='grey', facecolor='none', linewidth=2))
        else:
            self.info_label_pre.setText("Destination : N/A")
            self.info_label_pre.setStyleSheet("color: black;")            
            
        if self.radio_dest_afficher.isChecked():
            _,destination, _, _, _ = self.extracteur.obtenir_adresses()
            self.extracted_data = self.processed_data[-corr + 8*8*self.decodeur.nbr_ech_bit:-corr + 14*8*self.decodeur.nbr_ech_bit]
            couleur = 'red'
            label = destination
            label2 =''
            labelb=self.decodeur.decode[8*8:14*8]
            self.info_label_dest.setText(f"Destination : {destination}")
            self.info_label_dest.setStyleSheet("font-size: 22px; color: red;")
        # Tracer le rectangle de destination
            self.ax2.text(self.decodeur.nbr_ech_bit * (8 * 8) + 1, 1.25, 'Destination', color='red', fontsize=14)
            self.ax2.add_patch(plt.Rectangle((-corr+self.decodeur.nbr_ech_bit * (8 * 8), -1.1),-corr+ self.decodeur.nbr_ech_bit * (6 * 8), 2.2, edgecolor='red', facecolor='none', linewidth=2))
        else:
            self.info_label_dest.setText("Destination : N/A")
            self.info_label_dest.setStyleSheet("color: black;")

        if self.radio_src_afficher.isChecked():
            _,_, source, _, _ = self.extracteur.obtenir_adresses()
            self.extracted_data = self.processed_data[-corr + 14*8*self.decodeur.nbr_ech_bit:-corr + 20*8*self.decodeur.nbr_ech_bit]
            couleur = 'blue'
            label = source
            label2 =''
            labelb=self.decodeur.decode[14*8:20*8]
            self.info_label_src.setText(f"Source : {source}")
            self.info_label_src.setStyleSheet("font-size: 22px; color: blue;")
        # Tracer le rectangle de source
            
            self.ax2.text(self.decodeur.nbr_ech_bit * (14 * 8) + 1, 1.25, 'Source', color='blue', fontsize=14)
            self.ax2.add_patch(plt.Rectangle((-corr+self.decodeur.nbr_ech_bit * (14 * 8), -1.1),-corr+ self.decodeur.nbr_ech_bit * (6 * 8), 2.2, edgecolor='blue', facecolor='none', linewidth=2))
        else:
            self.info_label_src.setText("Source : N/A")
            self.info_label_src.setStyleSheet("color: black;")

        if self.radio_type_afficher.isChecked():
            _,_, _, ethertype, _ = self.extracteur.obtenir_adresses()
            self.extracted_data = self.processed_data[-corr + 20*8*self.decodeur.nbr_ech_bit:-corr + 22*8*self.decodeur.nbr_ech_bit]
            couleur = 'green'
            
            ethertype2=ethertype
            if ethertype == '08 00 ':
                ethertype2=ethertype2 + 'IPV4'
            if ethertype == '08 06 ':
                ethertype2 = ethertype2 + 'ARP'
            if ethertype == '86 dd ':
                ethertype2 = ethertype2 + 'IPV6'

            
            label = ethertype2
            label2 =''
            labelb=self.decodeur.decode[20*8:22*8]
            self.info_label_type.setText(f"Type : {ethertype2}")
            self.info_label_type.setStyleSheet("font-size: 22px; color: green;")
        # Tracer le rectangle de type
            
            self.ax2.text(self.decodeur.nbr_ech_bit * (20 * 8) + 1, 1.25, 'Type', color='green', fontsize=14)
            self.ax2.add_patch(plt.Rectangle((-corr+self.decodeur.nbr_ech_bit * (20 * 8), -1.1), -corr+self.decodeur.nbr_ech_bit * (2 * 8), 2.2, edgecolor='green', facecolor='none', linewidth=2))
        else:
            self.info_label_type.setText("Type : N/A")
            self.info_label_type.setStyleSheet("color: black;")

        if self.radio_data_afficher.isChecked():
            _,_, _, _, data = self.extracteur.obtenir_adresses()
            print(data)
            self.extracted_data = self.processed_data[-corr + 22*8*self.decodeur.nbr_ech_bit:]
            couleur = 'purple'
            label = data
            label2=''
            labelb=''
            if len(data)>30*3:
                label = data[:len(data)//2+1]
                label2 += data[len(data)//2+1:]
            self.info_label_data.setText(f"Data : {data}")
            self.info_label_data.setStyleSheet("font-size: 22px; color: purple;")
            if len(data)>50:
                self.info_label_data.setStyleSheet("font-size: 18px; color: purple;")
        # Tracer le rectangle de données
            self.ax2.text(self.decodeur.nbr_ech_bit * (22 * 8) + 1, 1.25, 'DATA', color='purple', fontsize=14)
            self.ax2.add_patch(plt.Rectangle((-corr+self.decodeur.nbr_ech_bit * (22 * 8), -1.1), len(self.processed_data) - self.decodeur.nbr_ech_bit * (22 * 8), 2.2, edgecolor='purple', facecolor='none', linewidth=2))
        else:
            self.info_label_data.setText("Data : N/A")
            self.info_label_data.setStyleSheet("color: black;")
  
    # Tracer la trame complète avec les données traitées

        self.ax.plot(self.extracted_data, color='{}'.format(couleur))
        self.ax.set_ylim(-1.5, 1.5)
        for i in range(len(labelb)):
            self.ax.text(i*self.decodeur.nbr_ech_bit+self.decodeur.nbr_ech_bit//3,1.1,"{}".format(labelb[i]), fontsize = 12, color='{}'.format(couleur) )
        
        self.ax.text(0,1.55,"{}".format(label), fontsize = 16, color='{}'.format(couleur) )
        self.ax.text(0,1.2,"{}".format(label2), fontsize = 16 , color='{}'.format(couleur))
    # Tracer la trame complète dans ax2
        self.ax2.plot(self.processed_data)
        self.ax2.set_ylim(-1.5, 1.5)
        self.ax2.set_title("Trame complète")

    # Rafraîchir les graphiques
        self.canvas.draw()
        self.canvas2.draw()



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    interface = Interface()
    interface.show()
    sys.exit(app.exec_())
