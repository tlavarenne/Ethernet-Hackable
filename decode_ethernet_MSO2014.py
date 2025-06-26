import matplotlib.pyplot as plt
import csv
import numpy as np
####################### EXTRACTION FICHIER CSV ######################



data=[]
f= open('trames/T0007CH1_Tek.CSV','rt')
df= csv.reader(f, delimiter=',')   #Delimiteur à adapter éventuellement
for index, row in enumerate(df):
	if len(row) == 0:
		continue
	if row[0] == 'Sample Interval':
		sample_interval = float(row[1].replace(",", ".")) #Remplacer les virgules par des points
	if index > 17:
		data.append(float(row[1])) #row a adapter
data = np.array(data)
data = data/max(data)


print("sample interval=", sample_interval)

###################### CALCUL ET SOUSTRACTION COMPOSANTE CONTINUE ################

data = data - np.mean(data)



###################### calage début signal #######################
index=0
while data[index]> -0.07:
	index+=1

data=data[index:]

########################DÉCODAGE DU MANCHESTER #####################"
D = 10e6 #Débit binaire 10BASE-T

nbr_ech_bit = int(round(1/sample_interval/D))
print("\nnbr ech bit=", nbr_ech_bit, 'ech/bit')

decode=''
i=nbr_ech_bit//4
while i < len(data) - nbr_ech_bit //2 :
	if data[i] > 0 and data[i+nbr_ech_bit//2] < 0:
		decode += '0'
	if data[i] < 0 and data[i+nbr_ech_bit//2] > 0:
		decode += '1'
	i=i+nbr_ech_bit

print()
print("trame binaire=", decode)

plt.plot(data)
plt.show(block=False)





######################## extraction des octets et affichage en hexa #####################"

## Suppression du preambule
i=0
while decode[i] == '1' and decode[i+1] == '0':
	i+=2

decode=decode[i+2:]

print(decode)

octets = ''
i = 0
while i < len(decode) - 8:
	byte = decode[i:i+8][::-1]  # On lit les bits LSB first
	octets+=hex(int(byte, 2))[2:].zfill(2) + ' '# Conversion en hexa
	i += 8

print("\nTrame complète en HEXA:")
print(octets)

# Affichage des octets
print("\nDestination MAC :")
print(octets[:6*3])

print("\nSource MAC :")
print(octets[6*3:12*3])

print("\nEtherType :")
ethertype = octets[12*3:14*3]


if ethertype ==  '08 00 ':
	print(ethertype, ' IPV4')
if ethertype ==  '08 06 ':
	print(ethertype,  ' ARP')
if ethertype ==  '86 dd ':
	print(ethertype,  ' IPV6')

print("\nDonnées après EtherType :")
DATA = octets[14*3:]
print(DATA)



plt.show()
