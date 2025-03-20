# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.core.files import File
from django.conf import settings
import os, ipfshttpclient, requests
from django.utils import timezone  # Import timezone

from .models import Request, FinalPapers, CustomUser, SubjectCode
from .encryption import encrypt_file, decrypt_file
from .a_encryption import a_encryption, a_decryption
from .blockchain import record_paper_upload, record_paper_download_event


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
            final_record = FinalPapers.objects.create(
                s_code=req.s_code,
                course=teacher_info["course"],
                semester=teacher_info["semester"],
                branch=teacher_info["branch"],
                subject=teacher_info["subject"]
            )
            final_record.paper.save(f"{req.s_code}.pdf", final_content, save=True)

            # Record blockchain transaction.
            receipt = record_paper_upload(hash_id, req.tusername)
            tx_hash = receipt.transactionHash.hex()
            final_record.blockchain_status = "Recorded"
            final_record.tx_hash = tx_hash
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

    for paper in queryset:
        try:
            # Fetch the associated request for this paper
            exam_request = Request.objects.get(s_code=paper.s_code, status="Finalized")
            exam_time = exam_request.exam_time

            time_difference = exam_time - now

            # Allow download only when the exam is 20 minutes away or less
            downloadable = time_difference <= datetime.timedelta(minutes=20)

        except Request.DoesNotExist:
            downloadable = False  # No associated request found

        final_papers_data.append({
            'exam_time': exam_time,
            'paper': paper,
            'downloadable': downloadable,
            'timediff': time_difference
        })

    if request.method == 'POST':  # Handle download requests
        paper_id = request.POST.get('paper_id')
        if paper_id:
            paper = get_object_or_404(FinalPapers, id=paper_id)  # Get Paper Object
            try:
                # Record download event on blockchain
                download_tx_hash = record_paper_download_event(
                    paper.id,  # Passing Paper's ID
                    request.user.username  # Superintendent's username
                )
                # Update the model
                paper.download_tx_hash = download_tx_hash
                paper.save()

            except Exception as e:
                messages.error(request, f"Error recording download on blockchain: {e}")

            # Serve the file for download
            file_path = paper.paper.path
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response['Content-Disposition'] = f'attachment; filename="{paper.s_code}.pdf"'
                return response

    return render(request, 'superintendent.html', {'final_papers_data': final_papers_data})




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