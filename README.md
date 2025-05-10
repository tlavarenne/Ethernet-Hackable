# Ethernet-Hackable
Fichiers Python et acquisitions (CSV et bin) liées à l'article "Ethernet à la loupe: de la couche physique au décodage des trames" du magazine Hackable n°61 juillet/août 2025, Editions Diamond.

# Ethernet 10BASE-T:

L'étude du protocole 10BASE-T décrite dans l'article a conduit à la création d'une interface graphique pyQT5 pour décoder les trames Ethernet.

script: decode_ethernet_10Mbps_Interface_Graphique.py

Les fichiers CSV sont à télécharger séparément. Bien sélectionner le bon modèle d'oscilloscope en rapport avec le fichier CSV à décoder.

Vidéo démonstration:

https://drive.google.com/file/d/1IcIyn7spNMZc0p1wGvt3BzvhHJLoFkX5/view?usp=drive_link


# Ethernet 100BASE-TX: 

Deux scripts sont fournis, un dans lequel les fichiers à charger sont à indiquer manuellement dans le fichier (éditeur python nécéssaire), un autre permettant l'execution en passant en argument le nom de fichier et éventuellement les paramètres nécéssaires:

- decode_ethernet100Mbps_avec_synchro_V10.py qui reprend l'intégralité du traitement décrit dans l'article Hackable en y rajoutant la resynchronisation en cas de perte du LFSR ainsi que l'analyse des trames avec SCAPY (https://scapy.net), module python à installer (sinon modifier la ligne 395 dans le script ANALYSE_SCAPY == False).

Ce script est à ouvrir avec un éditeur de fichier et il s'agit de modifier à la main le nom et le chemin des fichiers à traiter avant de l'executer.




- decode_ethernet100Mbps_avec_synchro_V10_AVEC_ARGUMENT.py qui permet une execution directement en passant les arguments nécéssaires:

  -f nom_du_fichier
  
  -s sampling_rate           (*fichiers binaires JMF uniquement*)
  
  -c voie 1 ou 2 si entrelacées       (*fichiers binaires JMF uniquement*)

**Exemples d'appel:**

python decode_ethernet100Mbps_avec_synchro_V10_AVEC_ARGUMENT.py -f Tek0004.csv   # pour un fichier CSV

python decode_ethernet100Mbps_avec_synchro_V10_AVEC_ARGUMENT.py -f CUT_RefCurve_2025-04-25_0_154619_1GSps_ping10ms.Wfm.bin -s 1e9 -c 2   # pour un fichier binaire JMF




