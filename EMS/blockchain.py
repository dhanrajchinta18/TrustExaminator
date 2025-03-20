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

def record_paper_upload(ipfs_hash, teacher_id):
    """
    Calls the smart contract function to record the paper upload event.
    ipfs_hash: The IPFS CID (string)
    teacher_id: The teacher's unique identifier (string)
    """
    # For simplicity, use the first Ganache account
    account = web3.eth.accounts[0]
    # Build and send the transaction; adjust gas if needed
    tx_hash = contract.functions.uploadPaper(ipfs_hash, teacher_id).transact({
        'from': account,
        'gas': 3000000
    })
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

def record_paper_download_event(paper_id, superintendent_username):
    """Records a paper download event on the blockchain.

    Args:
        paper_id: The ID of the paper being downloaded (from the FinalPapers model).
        superintendent_username: The username of the superintendent downloading the paper.

    Returns:
        The transaction hash of the blockchain transaction.
    """
    try:
        # For simplicity, use the first Ganache account
        account = web3.eth.accounts[0]

        # Build and send the transaction; adjust gas if needed
        tx_hash = contract.functions.recordDownload(paper_id, superintendent_username).transact({
            'from': account,
            'gas': 3000000
        })

        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt.transactionHash.hex()  # Return the transaction hash as a string

    except Exception as e:
        print(f"Error recording download event on blockchain: {e}")
        raise  # Re-raise the exception to be handled in the view
