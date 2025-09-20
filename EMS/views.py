# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required, user_passes_test # Import user_passes_test
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.files import File
from django.conf import settings
import os, ipfshttpclient, requests
from django.utils import timezone  # Import timezone
from web3 import Web3  # Import Web3

from .models import Request, FinalPapers, CustomUser, SubjectCode
from .encryption import encrypt_file, decrypt_file
from .a_encryption import a_encryption, a_decryption
from .blockchain import record_paper_upload, record_paper_download_event

# Load contract ABI (assuming it's loaded globally as contract_abi in blockchain.py or here)
import json
with open(settings.BLOCKCHAIN_ABI_PATH) as f:
    contract_json = json.load(f)
    contract_abi = contract_json["abi"]


def custom_404(request, exception):  # 'exception' argument is required by Django
    return render(request, '404.html', {'is_404_page': True}, status=404)

def user_login(request):
    if request.user.role == 'teacher':
        return redirect('teacher_dashboard')
    if request.user.role == "coe":
        return redirect('coe_dashboard')
    if request.user.role == 'superintendent':
        return redirect('st_dashboard')


@login_required(login_url='login')
@csrf_exempt
def user_logout(request):
    logout(request)
    return HttpResponseRedirect('/')


@login_required(login_url='login')
@csrf_exempt
def teacher_dashboard(request):
    # Retrieve teacher's requests separated by status.
    p_request = Request.objects.filter(tusername=request.user.username, status='Pending')
    a_request = Request.objects.filter(tusername=request.user.username).exclude(status='Pending')

    if request.method == 'POST':
        # If teacher accepts a request:
        if request.POST.get('accept'):
            b_id = request.POST.get('b_id')
            Request.objects.filter(tusername=request.user.username, id=b_id).update(status='Accepted')
            messages.success(request, 'Request Accepted! Click on Accepted Request Section to check your requests.', extra_tags='accept')
        else:
            # File upload branch for an accepted request.
            paper = request.FILES.get('paper')
            if not paper:
                messages.error(request, "No paper file provided.", extra_tags='upload')
                return render(request, 'teacher.html', {'p_request': p_request, 'a_request': a_request})

            req_id = request.POST.get('req_id')
            if not req_id:
                messages.error(request, "No request selected for upload.", extra_tags='upload')
                return render(request, 'teacher.html', {'p_request': p_request, 'a_request': a_request})

            try:
                store = Request.objects.get(id=req_id, tusername=request.user.username)
            except Request.DoesNotExist:
                messages.error(request, "The specified request was not found.", extra_tags='upload')
                return render(request, 'teacher.html', {'p_request': p_request, 'a_request': a_request})

            # **** Deadline Check ****
            now = timezone.now()
            if now > store.paper_deadline:
                messages.error(request, "The deadline for uploading this paper has passed.", extra_tags='upload')
                return render(request, 'teacher.html', {'p_request': p_request, 'a_request': a_request})
            # **** End Deadline Check ****

            # Encrypt the file (encrypt_file writes the file to settings.ENCRYPTION_ROOT).
            key = encrypt_file(paper)
            encrypted_filename = f"{paper.name}.encrypted"
            encrypted_filepath = os.path.join(settings.ENCRYPTION_ROOT, encrypted_filename)
            # Perform asymmetric encryption using a placeholder for the IPFS hash.
            arr = a_encryption("placeholder_hash", key, request.user.teacher_id)

            # Save teacher's private key for this request.
            private_key_filename = f"{request.user.teacher_id}_private_key.pem"
            private_key_filepath = os.path.join(settings.ENCRYPTION_ROOT, private_key_filename)
            with open(private_key_filepath, 'rb') as key_file:
                store.private_key.save(private_key_filename, File(key_file), save=True)

            # Update request: store encryption data and filename, then mark as Pending Finalization.
            store.enc_field = arr
            store.encrypted_file = encrypted_filename  # New field to store local filename.
            store.status = 'Pending Finalization'
            store.save()

            messages.success(request, 'Paper uploaded successfully! Awaiting finalization by COE.', extra_tags='upload')

    return render(request, 'teacher.html', {'p_request': p_request, 'a_request': a_request})



@login_required(login_url='login')
@csrf_exempt
def coe_dashboard(request):
    if request.method == "POST":
        s_code = request.POST.get('s_code')
        t_id = request.POST.get('t_id')

        # Fetch the request with status "Pending Finalization".
        req = Request.objects.filter(id=t_id, status="Pending Finalization").first()
        if not req:
            messages.error(request, "No pending finalization found for this request.", extra_tags='finalize')
            return redirect('coe_dashboard')

        if not req.encrypted_file:
            messages.error(request, "Encrypted file missing for this request. Please ask the teacher to re-upload.", extra_tags='finalize')
            return redirect('coe_dashboard')

        try:
            # Build local file path.
            file_path = os.path.join(settings.ENCRYPTION_ROOT, req.encrypted_file)
            # Connect to IPFS and add the file.
            api = ipfshttpclient.connect()
            ipfs_result = api.add(file_path)
            hash_id = ipfs_result["Hash"]

            # Attempt to copy the file inside IPFS; if this fails, raise an error.
            api.files.cp(f"/ipfs/{hash_id}", f"/papers/{req.encrypted_file}")

            # Fetch the file from the IPFS gateway.
            r = requests.get(f"http://127.0.0.1:8080/ipfs/{hash_id}")
            if r.status_code != 200:
                raise Exception("Failed to retrieve file from IPFS gateway.")

            # Decrypt the file using stored encryption details.
            dec_values = a_decryption([req.enc_field, req.private_key])
            final_content = decrypt_file(r, dec_values[0], req.s_code)

            # Create a FinalPapers record.
            teacher_info = CustomUser.objects.filter(username=req.tusername).values("course", "semester", "branch", "subject").first()
            if not teacher_info:
                raise Exception("Teacher details not found.")

            # Construct filename using s_code - Robust approach
            constructed_filename = f"{req.s_code}.pdf"
            if not constructed_filename:  # Fallback in case filename construction fails
                constructed_filename = "unknown_filename.pdf" # Default filename
                messages.warning(request, "Filename construction failed. Using default filename.") # Optional warning

            final_record = FinalPapers.objects.create(
                s_code=req.s_code,
                course=teacher_info["course"],
                semester=teacher_info["semester"],
                branch=teacher_info["branch"],
                subject=teacher_info["subject"],
                filename=constructed_filename
            )
            final_record.paper.save(f"{req.s_code}.pdf", final_content, save=True)

            # Record blockchain transaction.
            receipt, contract_paper_id = record_paper_upload(hash_id, constructed_filename, req.tusername) # MODIFIED: Get paperCount
            tx_hash = receipt.transactionHash.hex()
            final_record.blockchain_status = "Recorded"
            final_record.tx_hash = tx_hash
            final_record.contract_paper_id = contract_paper_id # MODIFIED: Store contract_paper_id
            final_record.save()

            # Only after successful processing, update the request status.
            req.status = "Finalized"
            req.save()

            # Remove the local encrypted file for security.
            if os.path.exists(file_path):
                os.remove(file_path)

            messages.success(request, "Paper finalized successfully and securely recorded.", extra_tags='finalize')
        except Exception as e:
            messages.error(request, f"Finalization error: {str(e)}", extra_tags="finalize")
            return redirect('coe_dashboard')

        return redirect('coe_dashboard')
    else:
        # GET: Show complete history of all requests.
        requests_data = Request.objects.all().values("tusername", "status")
        arr = []
        for r in requests_data:
            user_info = CustomUser.objects.filter(username=r["tusername"]).values("first_name", "last_name").first()
            teacher_name = f"{user_info['first_name']} {user_info['last_name']}" if user_info else r["tusername"]
            arr.append({"name": teacher_name, "status": r["status"]})
        return render(request, "coe.html", {"arr": arr})


from django.utils import timezone
import datetime

@login_required(login_url='login')
@csrf_exempt
def st_dashboard(request):  # Django's HttpRequest object
    queryset = FinalPapers.objects.all()
    final_papers_data = []

    now = timezone.now()  # Get the current time (time-zone aware)

    print("DEBUG (st_dashboard): Starting to process final_papers_data loop") # Debug 1

    for paper in queryset:
        try:
            # Fetch the associated request for this paper
            exam_request = Request.objects.filter(s_code=paper.s_code, status="Finalized").first()
            if exam_request:
                exam_time = exam_request.exam_time
                time_difference = exam_time - now
                downloadable = time_difference <= datetime.timedelta(minutes=20)
            else:
                downloadable = False

        except Request.DoesNotExist:
            downloadable = False

        final_papers_data.append({
            'exam_time': exam_time if exam_request else None,
            'paper': paper,
            'downloadable': downloadable,
            'timediff': time_difference if exam_request else None,
            'already_downloaded': paper.downloaded,  # Pass downloaded status to template
            'django_paper_id': paper.id, # Debug: Django FinalPapers ID
            'contract_paper_id': paper.contract_paper_id # Debug: Contract Paper ID
        })

    print("DEBUG (st_dashboard): final_papers_data prepared:") # Debug 2
    for item in final_papers_data: # Debug 3: Print details of each item in final_papers_data
        print(f"DEBUG (st_dashboard):   Django Paper ID: {item['django_paper_id']}, Contract Paper ID: {item['contract_paper_id']}, Downloadable: {item['downloadable']}, Already Downloaded: {item['already_downloaded']}")


    if request.method == 'POST':  # Handle download requests
        paper_id_str = request.POST.get('paper_id')
        print(f"DEBUG (st_dashboard): POST request received. paper_id_str from form: {paper_id_str}") # Debug 4
        if paper_id_str:
            try:
                paper_id = int(paper_id_str)
                print(f"DEBUG (st_dashboard): paper_id (int) to lookup (contract_paper_id): {paper_id}") # Debug 5 - Clarified debug message
                paper_instance = get_object_or_404(FinalPapers, contract_paper_id=paper_id) # MODIFIED: Lookup by contract_paper_id
                print(f"DEBUG (st_dashboard): FinalPapers instance found for contract_paper_id: {paper_id}, Django Paper ID: {paper_instance.id}, Contract Paper ID: {paper_instance.contract_paper_id}") # Debug 6 - Clarified debug message

                if paper_instance.downloaded:  # Check if already downloaded
                    messages.error(request, "This paper has already been downloaded.") # Optional message
                    return redirect('st_dashboard') # Redirect to dashboard or handle as needed

                try:
                    # Record download event on blockchain
                    download_tx_hash = record_paper_download_event(
                        paper_id, # Pass contract_paper_id (which is now 'paper_id' variable)
                        paper_instance.filename,
                        request.user.username
                    )
                    # Update the model
                    paper_instance.download_tx_hash = download_tx_hash
                    paper_instance.downloaded = True  # Set downloaded to True after successful download
                    paper_instance.save()

                except Exception as e:
                    messages.error(request, f"Error recording download on blockchain: {e}")

                # Serve the file for download
                file_path = paper_instance.paper.path
                with open(file_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type="application/pdf")
                    response['Content-Disposition'] = f'attachment; filename="{paper_instance.s_code}.pdf"'
                    return response

            except ValueError:
                messages.error(request, "Invalid paper ID format.")
        else:
            print("DEBUG (st_dashboard): paper_id_str is empty in POST request") # Debug 7

    return render(request, 'superintendent.html', {'final_papers_data': final_papers_data})


# New View for Transaction History (COE only)
from web3._utils.events import get_event_data

@login_required(login_url='login')
@user_passes_test(lambda u: u.role == 'coe')
def transaction_history_coe(request):
    if request.user.role != 'coe':
        messages.error(request, "You do not have permission to access this page.", extra_tags='access_denied')
        return render(request, 'transaction_history_coe.html', {'transactions': []}) # Or redirect to another page if preferred

    w3 = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_GANACHE_URL))

    # Build a dict of event ABIs from contract_abi (assumed to be imported/defined)
    event_abis = {item['name']: item for item in contract_abi if item.get('type') == 'event'}
    if not all(name in event_abis for name in ('PaperUploaded', 'PaperDownloaded')):
        messages.error(request, "Event ABIs not found in contract ABI.")
        return render(request, 'transaction_history_coe.html', {'transactions': []})

    # Pre-calculate event signature topics
    topics = {
        'Upload': "0x" + w3.keccak(text="PaperUploaded(uint256,string,string,string,uint256)").hex(),
        'Download': "0x" + w3.keccak(text="PaperDownloaded(uint256,uint256,string,string,uint256)").hex()
    }

    # Fetch logs for PaperUploaded
    uploaded_filter = w3.eth.filter({
        "address": settings.BLOCKCHAIN_CONTRACT_ADDRESS,
        "fromBlock": 0,
        "topics": [topics['Upload']]
    })
    uploaded_events = w3.eth.get_filter_logs(uploaded_filter.filter_id)

    # Fetch logs for PaperDownloaded
    downloaded_events = w3.eth.get_logs({
        'address': settings.BLOCKCHAIN_CONTRACT_ADDRESS,
        'fromBlock': 0,
        'toBlock': 'latest',
        'topics': [topics['Download']]
    })

    # Helper function to decode an event log
    def decode_event(event, event_type):
        abi = event_abis['PaperUploaded'] if event_type == 'Upload' else event_abis['PaperDownloaded']
        decoded = get_event_data(w3.codec, abi, event)
        # Try to retrieve the block timestamp; fallback to the decoded event's timestamp
        block = w3.eth.get_block(event['blockNumber'])
        ts = block.get('timestamp') or decoded['args'].get('timestamp')
        # Convert Unix timestamp (seconds) to a Python datetime object
        timestamp = datetime.datetime.fromtimestamp(ts) if ts else None
        print(timestamp)
        args = decoded['args']
        if event_type == 'Upload':
            initiator = args.get('uploader', '')
            paper_id = args.get('id', '')
        else:
            initiator = args.get('downloader', '')
            paper_id = args.get('paperId', '')
        return {
            'tx_hash': event['transactionHash'].hex(),
            'block_number': event['blockNumber'],
            'timestamp': timestamp,
            'event_type': event_type,
            'initiator': initiator,
            'filename': args.get('filename', ''),
            'paper_id': paper_id
        }

    transactions = ([decode_event(ev, 'Upload') for ev in uploaded_events] +
                    [decode_event(ev, 'Download') for ev in downloaded_events])
    transactions.sort(key=lambda x: x['timestamp'] or 0, reverse=True)

    return render(request, 'transaction_history_coe.html', {'transactions': transactions})



#
# @login_required(login_url='login')
# @user_passes_test(lambda u: u.role == 'coe')  # Restrict to COE role
# def transaction_history_coe(request):
#     web3_instance = Web3(Web3.HTTPProvider(settings.BLOCKCHAIN_GANACHE_URL))
#     contract_instance = web3_instance.eth.contract(
#         address=settings.BLOCKCHAIN_CONTRACT_ADDRESS,
#         abi=contract_abi
#     )
#
#     # Extract event ABIs from the contract ABI for decoding logs
#     paper_uploaded_event_abi = None
#     paper_downloaded_event_abi = None
#     for item in contract_abi:
#         if item.get('type') == 'event' and item.get('name') == 'PaperUploaded':
#             paper_uploaded_event_abi = item
#         elif item.get('type') == 'event' and item.get('name') == 'PaperDownloaded':
#             paper_downloaded_event_abi = item
#
#     if not paper_uploaded_event_abi or not paper_downloaded_event_abi:
#         messages.error(request, "Event ABIs not found in contract ABI.")
#         return render(request, 'transaction_history_coe.html', {'transactions': []})
#
#     # Get event signature hashes for filtering logs.
#     # (Make sure the string matches the Solidity event exactly.)
#     paper_uploaded_event_signature_hash = "0x" + web3_instance.keccak(text="PaperUploaded(uint256,string,string,string,uint256)").hex()
#     paper_downloaded_event_signature_hash = "0x" + web3_instance.keccak(text="PaperDownloaded(uint256,uint256,string,string,uint256)").hex()
#
#     # Fetch event logs for PaperUploaded using eth.filter
#     uploaded_event_filter = web3_instance.eth.filter({
#         "address": settings.BLOCKCHAIN_CONTRACT_ADDRESS,
#         "fromBlock": 0,
#         "topics": [paper_uploaded_event_signature_hash]
#     })
#     uploaded_events = web3_instance.eth.get_filter_logs(uploaded_event_filter.filter_id)
#
#     # Fetch PaperDownloaded events using get_logs
#     downloaded_events = web3_instance.eth.get_logs({
#         'address': settings.BLOCKCHAIN_CONTRACT_ADDRESS,
#         'fromBlock': 0,
#         'toBlock': 'latest',
#         'topics': [paper_downloaded_event_signature_hash]
#     })
#
#     transactions = []
#
#     # Decode PaperUploaded events
#     for event in uploaded_events:
#         print("DEBUG (transaction_history_coe): Uploaded Event Keys:", event.keys())
#         decoded_event = get_event_data(web3_instance.codec, paper_uploaded_event_abi, event)
#         transactions.append({
#             'tx_hash': event['transactionHash'].hex(),
#             'block_number': event['blockNumber'],
#             'timestamp': web3_instance.eth.get_block(event['blockNumber'])['timestamp'],
#             'event_type': 'Upload',
#             'initiator': decoded_event['args']['uploader'],
#             'filename': decoded_event['args']['filename'],
#             'paper_id': decoded_event['args']['id']
#         })
#
#     # Decode PaperDownloaded events
#     for event in downloaded_events:
#         print("DEBUG (transaction_history_coe): Downloaded Event Keys:", event.keys())
#         decoded_event = get_event_data(web3_instance.codec, paper_downloaded_event_abi, event)
#         transactions.append({
#             'tx_hash': event['transactionHash'].hex(),
#             'block_number': event['blockNumber'],
#             'timestamp': web3_instance.eth.get_block(event['blockNumber'])['timestamp'],
#             'event_type': 'Download',
#             'initiator': decoded_event['args']['downloader'],
#             'filename': decoded_event['args']['filename'],
#             'paper_id': decoded_event['args']['paperId']
#         })
#
#     # Sort transactions by timestamp in descending order (newest first)
#     transactions.sort(key=lambda x: x['timestamp'], reverse=True)
#
#     context = {'transactions': transactions}
#     return render(request, 'transaction_history_coe.html', context)


def get_teachers(request):
    course = request.POST.get('course')
    semester = request.POST.get('semester')
    branch = request.POST.get('branch')
    subject = request.POST.get('subject')

    # Exclude teachers with active requests.
    active_teachers = Request.objects.filter(
        status__in=['Pending', 'Accepted', 'Uploaded', 'Pending Finalization']
    ).values_list('tusername', flat=True).distinct()

    s_code_qs = SubjectCode.objects.filter(subject=subject).values()
    if not s_code_qs:
        return JsonResponse({'error': 'Subject code not found for the given subject'}, status=400)
    s_code = s_code_qs[0]['s_code']

    # Return requests that are pending finalization for this subject.
    queryset2 = Request.objects.filter(s_code=s_code, status='Pending Finalization').values('id')

    queryset = CustomUser.objects.filter(
        course=course,
        semester=semester,
        branch=branch,
        subject=subject
    ).exclude(username__in=active_teachers).values()

    data = {
        'queryset': list(queryset),
        's_code': s_code,
        'queryset2': list(queryset2)
    }
    return JsonResponse(data)



def add_teacher(request):
    s_code = request.POST.get('s_code', None)
    syllabus = request.FILES.get('syllabus', None)
    q_pattern = request.FILES.get('q_pattern', None)
    t_id = request.POST.get('g_id')
    deadline = request.POST.get('paper_deadline', None)
    exam_time = request.POST.get('exam_time',None)
    username = CustomUser.objects.filter(id=t_id).values('username')
    print(s_code, syllabus, t_id)
    Request.objects.create(
        tusername=username[0]['username'],
        s_code=s_code,
        syllabus=syllabus,
        q_pattern=q_pattern,
        paper_deadline=deadline,
        exam_time = exam_time
    )
    new_teacher = CustomUser.objects.filter(username=username[0]['username']).values()
    return JsonResponse({'new_teacher': list(new_teacher)})