import csv
import numpy as np
from collections import deque
import subprocess
# import os
import argparse


    
# Fonction pour lire les données depuis un fichier CSV
def lire_donnees_CSV(chemin, ignore_lignes=15):
    """
    Lit un fichier CSV produit par un oscillosocpe TekTronix et extrait les données sous forme de tableau. À ADAPTER SELON LE MODÈLE D'OSCILLOSCOPE.
    Ignore les premières lignes spécifiées par `ignore_lignes`, puis extrait la donnée dans la deuxième colonne.

    Arguments:
        chemin (str): Le chemin du fichier CSV.
        ignore_lignes (int): Le nombre de lignes à ignorer au début du fichier (ici 15).

    Renvoie:
       Un tuple contenant :
            - periode_echantillon (float): La période d'échantillonnage, extrait de la ligne contenant "Sample Interval".
            - donnees (np.array): Les données extraites du fichier CSV (valeurs numériques de la deuxième colonne ici).
    """
    donnees = []
    periode_echantillon = None

    with open(chemin, 'rt') as f:
        df = csv.reader(f)
        for index, row in enumerate(df):
            if not row:
                continue
            # Trouver la ligne contenant l'intervalle d'échantillon
            if row[0].strip() == 'Sample Interval':
                periode_echantillon = float(row[1].replace(",", "."))
            # Après avoir ignoré les premières lignes, ajouter les données
            elif index > ignore_lignes:
                try:
                    donnees.append(float(row[1]))
                except (ValueError, IndexError):
                    continue

    if periode_echantillon is None:
        raise ValueError("Sample Interval non trouvé dans le fichier.")

    return periode_echantillon, np.array(donnees)


def lire_donnees_bin(chemin, fs=500e6, dtype=np.float32, count=None, deinterleave=False):
    """
    Lit un fichier binaire produit par un oscilloscope Rhode & Schwarz (JMF) et extrait les données sous forme de tableau.
    Peut également désentrelacer les données si elles proviennent de deux voies entrelacées.

    Arguments :
        chemin (str) : Chemin vers le fichier binaire.
        fs (float) : Fréquence d'échantillonnage en Hz (par défaut 500 MHz).
        dtype (type) : Type des échantillons (par défaut np.float32).
        count (int, optionnel) : Nombre d'échantillons à lire (None pour tout lire).
        deinterleave (bool | int) : 
            - False : pas de désentrelacement (données brutes)
            - 1 : extrait la voie 1 (échantillons pairs)
            - 2 : extrait la voie 2 (échantillons impairs)

    Renvoie :
        tuple :
            - periode_echantillon (float) : Période d’échantillonnage (1 / fs).
            - donnees (np.ndarray) : Données extraites du fichier.
    """
    if count is not None:
        donnees = np.fromfile(chemin, dtype=dtype, count=count)
    else:
        donnees = np.fromfile(chemin, dtype=dtype)

    if deinterleave == 1:
        donnees = donnees[::2]  # Voie 1 (échantillons pairs)
    elif deinterleave == 2:
        donnees = donnees[1::2]  # Voie 2 (échantillons impairs)

    periode_echantillon = 1 / fs
    return periode_echantillon, donnees


# Fonction de prétraitement du signal MLT-3 (Manchester Level Transmission)
def pretraitement_signal_mlt3(donnees, periode_echantillon, seuil):
    """
    Effectue le prétraitement du signal MLT-3 :
    - Supprime la composante continue au début du signal.
    - Centre et normalise le signal.
    - Applique la mise en forme MLT-3 par rapport au seuil choisi: défaut = 0.4
    - Effectue un calage sur la première transition.

    Arguments:
        donnees (np.array): Le signal brut à traiter.
        periode_echantillon (float): L'intervalle d'échantillonnage du signal.
        seuil (float): Le seuil pour la mise en forme MLT-3.

    Renvoie:
        Un tuple contenant :
            - signal_mlt3 (np.array): Le signal MLT-3 après traitement.
            - nbr_ech_bit (int): Le nombre d'échantillons par bit dans le signal.
    """
    
    i = 0
    while i < len(donnees) and donnees[i] < 0.05:
        i += 1
    donnees = donnees[i:]

    # Centrage et normalisation
    donnees = donnees - np.mean(donnees)  # Soustraction de la moyenne (centrage)
    donnees = donnees / np.max(np.abs(donnees))  # Normalisation
    
    # Mise en forme MLT-3 : transformation en -1, 0, +1
    signal_mlt3 = np.zeros_like(donnees)
    signal_mlt3[donnees > seuil] = 1
    signal_mlt3[donnees < -seuil] = -1

    # Calcul du nombre d'échantillons par bit (en fonction de l'intervalle d'échantillonnage et de la vitesse de transmission)
    nbr_ech_bit = int(1 / (periode_echantillon * 125e6))
    print("nbr_ech_bit =", nbr_ech_bit)

    # Calage sur la première transition
    transitions = np.where(signal_mlt3[:-1] != signal_mlt3[1:])[0]
    if len(transitions) > 0:
        debut = transitions[0] + 1
        donnees = donnees[debut:]
        signal_mlt3 = signal_mlt3[debut:]
    return signal_mlt3, nbr_ech_bit



def decode_mlt3(signal_mlt3, nbr_ech_bit):
    """
    Décode un signal MLT-3 en une chaîne binaire.

    Arguments:
        signal_mlt3 (np.array): Le signal MLT-3 après prétraitement.
        nbr_ech_bit (int): Le nombre d'échantillons par bit.

    Renvoie:
        str: La chaîne binaire décodée.
    """
    bits_decodes_mlt3 = []
    indice = 0
    longueur = len(signal_mlt3)

    # Parcours du signal MLT-3 pour extraire les bits
    while indice + 2 * nbr_ech_bit < longueur:
        valeur_courante = signal_mlt3[indice + nbr_ech_bit // 2]
        valeur_suivante = signal_mlt3[indice + nbr_ech_bit + nbr_ech_bit // 2]

        # Si les valeurs sont différentes, il s'agit d'un '1'
        if valeur_courante != valeur_suivante:
            bits_decodes_mlt3.append('1')
            index_niveau_suivant = indice
            while index_niveau_suivant < longueur and signal_mlt3[index_niveau_suivant ] == valeur_courante:  # Synchro sur les transitions
                index_niveau_suivant += 1
            if index_niveau_suivant == indice:
                index_niveau_suivant += 1  # évite boucle infinie
            indice = index_niveau_suivant
        else:
            bits_decodes_mlt3.append('0')
            indice += nbr_ech_bit

    return ''.join(bits_decodes_mlt3)


# Fonction pour trouver un état initial possible en fonction d'un motif
def trouve_etat_init(nbr_bits, sync_idle):
    """
    Recherche un état initial dans un tableau d'états possibles qui valide la synchronisation (en vérifiant un motif "111111111111...").

    Arguments:
        nbr_bits (int): Le nombre de bits dans l'état initial.
        sync_idle (str): Le motif de synchronisation à rechercher.

    Renvoie:
        Un tuple contenant :
            - etat (list): L'état initial trouvé.
            - sync (bool): Indique si la synchronisation a été réussie.
    """
    etat_initiaux = [[int(bit) for bit in bin(i)[2:].zfill(nbr_bits)] for i in range(2**nbr_bits)]
    for etat in etat_initiaux:
        if "1" * 40 in descramble_etat_initial(sync_idle, etat):  # Vérifie si le motif "11111" est dans les 50 premiers bits
            sync = True
            return etat, sync
    return None, False



def descramble_etat_initial(chaine_scramblee, etat_initial):
    """
    Applique un LFSR (Linear Feedback Shift Register) pour débrouiller un flux binaire grâce à un état initial donné.
    Fonction utilisée uniquement pour trouver l'état initial du LFSR soit au début soit en cas de perte de synchro.

    Arguments:
        chaine_scramblee (str): Le flux binaire à décramblier.
        etat_initial (list): L'état initial du LFSR.

    Renvoie:
        str: Le flux binaire après débrouillage.
    """
    lfsr = etat_initial
    chaine_descramblee = ''

    for bit in chaine_scramblee:
        bit_scramble = int(bit)
        ldd = lfsr[8] ^ lfsr[10]  # Calcul du bit LFSR
        bit_descramble = bit_scramble ^ ldd  # Applique le XOR
        chaine_descramblee += str(bit_descramble)
        lfsr = [ldd] + lfsr[:-1]  # Décalage des bits du LFSR

    return chaine_descramblee


# Fonction principale de débrouillage
def descramble(chaine_scramblee, etat_initial, sync, nbr_bits_traites, offset):    
    """
    Débrouille un flux binaire en utilisant un LFSR et l'état initial trouvé précédemment lors de la recherche.
    La fonction gère également le découpage et la synchronisation des trames.

    Arguments:
        chaine_scramblee (str): Le flux binaire à débrouiller.
        etat_initial (list): L'état initial du LFSR.
        sync (bool): Indicateur de synchronisation.

    Renvoie:
        Un tuple contenant :
            - trames_descramblees (list): Une liste des trames débrouillées.
            - nbr_bits_traites (int): Le nombre de bits traités.
            - sync (bool): Indicateur de synchronisation.
    """

    lfsr = etat_initial
    tampon = deque()
    trames_descramblees = []
    index_trames=[]
    trame_courante = ''
    dans_une_trame = False
    compteur_desynchro = 0
    seuil_perte_synchro = 100  # Si perte synchro, on s'affole pas tout de suite... (à adapter?)

    compteur_timeout = 0  # Initialiser compteur de timeout
    MAX_BITS_SANS_FIN = 30000 # Timeout après 30000 échantillons sans marqueur de fin si trame corrompue
 
    if etat_initial is None:
        return '', nbr_bits_traites +10, index_trames, False  # Pas d'état initial --> saute 10 bits (à adapter?)

    for bit in chaine_scramblee:
        bit_scramble = int(bit)
        ldd = lfsr[8] ^ lfsr[10]  # Calcul du bit LFSR
        bit_descramble = bit_scramble ^ ldd
        lfsr = [ldd] + lfsr[:-1]

        tampon.append(str(bit_descramble))
        nbr_bits_traites += 1

        # Limiter la taille du tampon s'il dépasse 200 échantillons (à adapter si nécessaire)
        if len(tampon) > 200:
            tampon.popleft()

        chaine_courante = ''.join(tampon)

        # Nettoyage si IDLE détecté
        if idle in chaine_courante:
            idx = chaine_courante.find(idle)
            reste = chaine_courante[idx + len(idle):]
            tampon = deque('1111111111' + reste)  # On s'arrange pour laisser quelques IDLE dans le tampon

        # Détecter le début de la trame avec une séquence supplémentaire après marqueur_debut
        if not dans_une_trame and marqueur_debut + '01011010110101101011' in chaine_courante:
            dans_une_trame = True  # On indique qu'on est en train de traiter une trame
            print("Début de trame détecté")
            index_trames.append(offset + nbr_bits_traites)
            trame_courante = chaine_courante.split(marqueur_debut, 1)[1]
            trame_courante = marqueur_debut + trame_courante
            tampon = deque(trame_courante)
            compteur_timeout = 0  # Réinitialisation du compteur de timeout dès le début de la trame

        elif dans_une_trame:  # Si on est dans une trame valide
            trame_courante += str(bit_descramble)

            # Incrémenter le compteur de timeout à chaque itération dans la trame
            compteur_timeout += 1

            if marqueur_fin in trame_courante:  # On a détecté une fin de trame
                contenu, reste = trame_courante.split(marqueur_fin, 1)
                trames_descramblees.append(contenu + marqueur_fin)
                print("Trame ajoutée")
                tampon = deque(reste)
                trame_courante = ''
                dans_une_trame = False  # On sort de la trame
                compteur_timeout = 0  # Réinitialiser le compteur de timeout

            # Si trop d'échantillons ont été traités sans trouver la fin de la trame
            elif compteur_timeout >= MAX_BITS_SANS_FIN:
                print("Timeout atteint, pas de marqueur de fin trouvé. Réinitialisation.")
                tampon.clear()  # Réinitialiser le tampon pour tenter de trouver une nouvelle trame
                trame_courante = ''
                dans_une_trame = False
                compteur_timeout = 0  # Réinitialiser le compteur de timeout

        # Suivi de la synchronisation
        if not dans_une_trame:
            if any(m in chaine_courante for m in (marqueur_debut, marqueur_fin, idle)):  
                compteur_desynchro = 0  # Réinitialiser le compteur si on trouve un marqueur
            else:  # Les bits débrouillés ne correspondent à aucun motif idle, début de trame ou fin de trame = perte de synchro
                compteur_desynchro += 1
                if compteur_desynchro > seuil_perte_synchro:  # On crie pas tout de suite....
                    sync = False
                    compteur_desynchro = 0
                    return trames_descramblees, nbr_bits_traites, index_trames, sync  # Renvoyer les trames, le nombre de bits et l'état de synchro
    return trames_descramblees, nbr_bits_traites, index_trames, sync 


# Fonction pour décoder un flux binaire en utilisant le codage 5B/4B
def decode_5b_4b(donnees):
    return ''.join(table_5b_4b.get(donnees[i:i+5], '') for i in range(0, len(donnees), 5))

# Fonction pour effectuer un échange des paquets de 4 bits
def echange_paquet(donnees_binaires):
    return ''.join(donnees_binaires[i+4:i+8] + donnees_binaires[i:i+4] for i in range(0, len(donnees_binaires), 8))

# Fonction pour convertir un flux binaire en hexadécimal
def binaire_vers_hexa(donnees_binaires):
    return ''.join(hex(int(donnees_binaires[i:i+8], 2))[2:].zfill(2) for i in range(0, len(donnees_binaires), 8))

# Codes ANSI pour les couleurs
class Couleurs:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'  # Réinitialise la couleur
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
# Table de conversion 5B/4B
table_5b_4b = {
    "11110": "0000", "01001": "0001", "10100": "0010", "10101": "0011",
    "01010": "0100", "01011": "0101", "01110": "0110", "01111": "0111",
    "10010": "1000", "10011": "1001", "10110": "1010", "10111": "1011",
    "11010": "1100", "11011": "1101", "11100": "1110", "11101": "1111",
    "11000": "J",  "10001": "K",  "01101": "T",  "00111": "R"
}




##################################################################
###################### Programme principal: ###################### 
##################################################################

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--filename", help="nom de fichier")
parser.add_argument("-s", "--samprate", help="frequence d''echantillonnage")
parser.add_argument("-c", "--channel",  help="voie de mesure")
args=parser.parse_args()
if args.filename:
    f3=args.filename
else:
    f3 = 'RefCurve_2025-04-25_0_154619_1GSps_ping10ms.Wfm.bin' # f3, fs = 1e9, deux voies deinterleave = 1 ou 2

if args.samprate:
    fs=float(args.samprate)
else:
    fs=1E9

if args.channel:
    ch=int(args.channel)
else:
    ch=1
print(f"{f3} fs={fs} ch={ch}")

if "csv" in f3: # Fichiers CSV: TL
    periode_echantillon, donnees = lire_donnees_CSV(f3)
else:           # Fichiers binaires Rhode & Schwarz: JMF
    print("lecture fichier binaire")
    periode_echantillon, donnees = lire_donnees_bin(f3, fs=fs, dtype=np.float32, count=None, deinterleave=ch)

print(len(donnees))

# Prétraitement:
signal_mlt3, nbr_ech_bit = pretraitement_signal_mlt3(donnees, periode_echantillon, seuil=0.4)


print("nbr echantillons:", len(donnees))
print("nbr bits:", len(donnees)//nbr_ech_bit)
print("durées acquisition:", len(donnees)*periode_echantillon*1000, 'ms')


# décodage MLT3
bits_decodes_mlt3 = decode_mlt3(signal_mlt3, nbr_ech_bit)


# paramètres pour le traitement de la chaine binaire
idle = '11111111111111111111'   # 4 motifs IDLE
marqueur_debut = '111111100010001'  #  IDLE + JK (début de trame)
marqueur_fin = '011010011111111'    # TR +  IDLE (fin de trame)
nbr_bits = 11  # LFSR registre 11 bits
index = 0
sync = False  # Pour lancer une première synchro LFSR
compteur_trame = 1 # initialise le compteur de trame

ANALYSE_SCAPY=True # True: Analyse des trames avec scapy

nbr_bits_traites = 0

toutes_les_trames = []
tous_les_indexs = []

while index < len(bits_decodes_mlt3):
    if not sync:
        state_init, sync = trouve_etat_init(nbr_bits, bits_decodes_mlt3[index:index + 50])
    
    trames_descramblees, nbr_bits_traites, index_trames, sync = descramble(bits_decodes_mlt3[index:], state_init, sync, 0, offset=index)
    
    # ====> On traite directement les nouvelles trames !
    for i, frame in enumerate(trames_descramblees):
        index_debut = frame.find(marqueur_debut)
        index_fin = frame.find(marqueur_fin, index_debut)

        if index_debut == -1 or index_fin == -1:
            continue  # Mauvaise trame, on saute

        trame_5b = frame[index_debut + len(marqueur_debut):index_fin]
        if not trame_5b:
            continue

        trame = decode_5b_4b(trame_5b)
        trame_echangee = echange_paquet(trame)
        hex_trame = binaire_vers_hexa(trame_echangee)

        if not hex_trame or len(hex_trame) < 42:
            continue  # Petite trame, on ignore
        
        print(f"\nTrame {compteur_trame}:")
        print("*************************************************************")
        print("index en bits:", index_trames[i])
        print("index en temps relatif:", index_trames[i]*nbr_ech_bit*periode_echantillon*1000, "ms")
        print(f"{Couleurs.HEADER}{hex_trame[:14]}{Couleurs.ENDC}"
              f"{Couleurs.WARNING}{hex_trame[14:26]}{Couleurs.ENDC}"
              f"{Couleurs.OKBLUE}{hex_trame[26:38]}{Couleurs.ENDC}"
              f"{Couleurs.FAIL}{hex_trame[38:42]}{Couleurs.ENDC}"
              f"{Couleurs.OKGREEN}{hex_trame[42:]}{Couleurs.ENDC}")
        print(f"{Couleurs.HEADER}\nPreambule: 55{hex_trame[:14]}{Couleurs.ENDC}")
        print(f"{Couleurs.WARNING}\nDEST MAC: {hex_trame[14:26]}{Couleurs.ENDC}")
        print(f"{Couleurs.OKBLUE}\nSOURCE MAC: {hex_trame[26:38]}{Couleurs.ENDC}")
        print(f"{Couleurs.FAIL}\nETHERTYPE: {hex_trame[38:42]}{Couleurs.ENDC}")

        compteur_trame += 1

        if ANALYSE_SCAPY:
            from scapy.all import Ether, hexdump
            hex_trame = hex_trame.split('d', 1)[-1]
            hex_trame = hex_trame[1:]
            print("ANALYSE SCAPY:")
            raw_bytes = bytes.fromhex(hex_trame)
            pkt = Ether(raw_bytes)
            pkt.show()
            hexdump(pkt)

    # ===> Ensuite seulement, avance l'index
    index += nbr_bits_traites

