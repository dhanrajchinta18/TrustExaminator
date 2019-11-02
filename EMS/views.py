from django.shortcuts import render,redirect
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models import *
from .encryption import *
from .a_encryption import *
from django.conf import settings
from django.core.files import File
import os, requests

# Create your views here.
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
	p_request = Request.objects.filter(tusername=request.user.username,status='Pending')
	a_request = Request.objects.filter(tusername=request.user.username).exclude(status='Pending')
	if request.method == 'POST':
		if request.POST.get('accept'):
			username = request.user.username
			b_id = request.POST['b_id']
			Request.objects.filter(tusername=username,id=b_id).update(status='Accepted')
			messages.success(request, 'Request Accepted! Click on Accepted Request Section on check your requests.',extra_tags='accept')
		else:
			paper = request.FILES.get('paper',None)
			key = encrypt_file(paper)
			file_ = open(os.path.join(settings.ENCRYPTION_ROOT,str(paper)+'.encrypted'),'rb')
			s_file = File(file_)
			queryset, created = Request.objects.update_or_create(tusername=request.user.username,defaults = {'status':'Uploaded'})
			store = Request.objects.get(tusername=request.user.username)
			store.paper.save(str(paper)+'.encrypted',s_file,save=True)
			hash_id = Request.objects.filter(tusername=request.user.username).values('paper')
			arr = a_encryption(hash_id[0]['paper'],key,request.user.teacher_id)
			file_ = open(os.path.join(settings.ENCRYPTION_ROOT,request.user.teacher_id+'_private_key.pem'),'rb')
			p_file = File(file_)
			queryset,created = Request.objects.update_or_create(tusername=request.user.username,defaults = {'enc_field':arr})
			store.private_key.save(request.user.teacher_id+'_private_key.pem',p_file,save=True)
			messages.success(request, 'Paper uploaded successfully!', extra_tags='upload')
	return render(request,'teacher.html',{'p_request':p_request,'a_request':a_request})

@login_required(login_url='login')
@csrf_exempt
def coe_dashboard(request):
	if request.method == "POST":
		s_code = request.POST['s_code']
		t_id = request.POST['t_id']
		Request.objects.filter(s_code=s_code).exclude(id=t_id).delete()
		queryset,created = Request.objects.update_or_create(id=t_id,defaults={'status':'Finalized'})
		messages.success(request, 'Paper has been finalized and sent to respective superintendent.')
	requests = Request.objects.values('tusername','status')
	arr = []
	for r in requests:
		name = CustomUser.objects.filter(username=r['tusername']).values('first_name','last_name')
		arr.append({'name':name[0]['first_name']+ " " + name[0]['last_name'],'status':r['status']})
	return render(request,'coe.html',{'arr':arr})

@login_required(login_url='login')
@csrf_exempt
def st_dashboard(request):
	f_papers = Request.objects.filter(status='Finalized').values('tusername','enc_field','private_key','paper')
	r = requests.get('http://localhost:8080/ipfs/'+f_papers[0]['paper'])
	#arr = a_decryption([f_papers[0]['enc_field'],f_papers[0]['private_key']])
	return render(request,'superintendent.html')

def get_teachers(request):
	course = request.POST.get('course',None)
	semester = request.POST.get('semester',None)
	branch = request.POST.get('branch',None)
	subject = request.POST.get('subject',None)
	queryset1 = Request.objects.values('tusername').distinct()
	s_code = SubjectCode.objects.filter(subject=subject).values()
	queryset2 = Request.objects.filter(s_code=s_code[0]['s_code'],status='Uploaded').values()
	queryset = CustomUser.objects.filter(course=course,semester=semester,branch=branch,subject=subject).exclude(username__in=queryset1).values()
	data = { 'queryset':list(queryset),'s_code':s_code[0]['s_code'],'queryset2':list(queryset2) }
	return JsonResponse(data)

def add_teacher(request):
	s_code = request.POST.get('s_code',None)
	syllabus = request.FILES.get('syllabus',None)
	q_pattern = request.FILES.get('q_pattern',None)
	t_id = request.POST.get('g_id')
	deadline = request.POST.get('deadline',None)
	username = CustomUser.objects.filter(id=t_id).values('username')
	print(s_code,syllabus,t_id)
	Request.objects.create(tusername=username[0]['username'],s_code=s_code,syllabus=syllabus,q_pattern=q_pattern,deadline=deadline)
	new_teacher = CustomUser.objects.filter(username=username[0]['username']).values()
	return JsonResponse({'new_teacher':list(new_teacher)})