from cryptography.fernet import Fernet
from django.conf import settings
import os

def encrypt_file(paper):

	key = Fernet.generate_key()
	input_file = paper
	output_file = os.path.join(settings.ENCRYPTION_ROOT,str(paper)+'.encrypted')

	data = input_file.read()

	fernet = Fernet(key)
	encrypted = fernet.encrypt(data)

	with open(output_file, 'wb') as f:
	    f.write(encrypted) 

	return key


def decrypt_file(paper):

	from cryptography.fernet import Fernet
	input_file = 'paper.encrypted'
	output_file = 'decrypted_paper.pdf'

	with open(input_file, 'rb') as f:
	    data = f.read()

	fernet = Fernet(key)
	encrypted = fernet.decrypt(data)

	with open(output_file, 'wb') as f:
	    f.write(encrypted)