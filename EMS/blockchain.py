import json
from web3 import Web3
from django.conf import settings

# Connect to Ganache using the URL from settings
web3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_GANACHE_URL))
if not web3.is_connected():
    raise Exception(f"Unable to connect to Ganache at {settings.BLOCKCHAIN_GANACHE_URL}")

# Load the contract ABI and address from settings
with open(settings.BLOCKCHAIN_ABI_PATH) as f:
    contract_json = json.load(f)
    contract_abi = contract_json["abi"]

contract_address = settings.BLOCKCHAIN_CONTRACT_ADDRESS
contract = web3.eth.contract(address=contract_address, abi=contract_abi)

def record_paper_upload(ipfs_hash, filename, teacher_id):
    """Calls the smart contract function to record paper upload."""
    account = web3.eth.accounts[0]

    print("DEBUG (blockchain.py): record_paper_upload - Arguments:")
    print(f"DEBUG (blockchain.py): ipfs_hash: {ipfs_hash}, type: {type(ipfs_hash)}")
    print(f"DEBUG (blockchain.py): filename: {filename}, type: {type(filename)}")
    print(f"DEBUG (blockchain.py): teacher_id: {teacher_id}, type: {type(teacher_id)}")

    # Forcefully prefix event signature hash with "0x"
    paper_uploaded_event_signature_hash = "0x" + web3.keccak(text="PaperUploaded(uint256,string,string,string,uint256)").hex()
    print(f"DEBUG (blockchain.py): Forcefully prefixed PaperUploaded Event Signature Hash: {paper_uploaded_event_signature_hash}")

    # Build and send transaction with explicit topics (even if not strictly needed)
    tx_hash = contract.functions.uploadPaper(ipfs_hash, filename, teacher_id).transact({
        'from': account,
        'gas': 3000000,
        'topics': [paper_uploaded_event_signature_hash]  # Include topics explicitly
    })
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt, contract.functions.paperCount().call() # MODIFIED: Return receipt and paperCount

def record_paper_download_event(paper_id, filename, superintendent_username):
    """Records paper download event on blockchain."""
    try:
        account = web3.eth.accounts[0]

        # Forcefully prefix event signature hash with "0x"
        paper_downloaded_event_signature_hash = "0x" + web3.keccak(text="PaperDownloaded(uint256,uint256,string,string,uint256)").hex()
        print(f"DEBUG (blockchain.py): Forcefully prefixed PaperDownloaded Event Signature Hash: {paper_downloaded_event_signature_hash}")

        # Build and send transaction with explicit topics (even if not strictly needed)
        tx_hash = contract.functions.recordDownload(paper_id, filename, superintendent_username).transact({
            'from': account,
            'gas': 3000000,
            'topics': [paper_downloaded_event_signature_hash] # Include topics explicitly
        })

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt.transactionHash.hex()

    except Exception as e:
        print(f"Error recording download event on blockchain: {e}")
        raise