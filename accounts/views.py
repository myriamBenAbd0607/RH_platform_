from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Contract
from .forms import ContractForm
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserRoleForm,
    EmployeeForm, EmployeeStatusForm
)
from .models import CustomUser

# Helper functions pour vérifier les permissions
def is_admin(user):
    return user.role == 'ADMIN'

def is_manager_or_admin(user):
    return user.role in ['ADMIN', 'MANAGER']


# ============ VUES D'AUTHENTIFICATION ============

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Compte créé avec succès !')
            return redirect('/accounts/dashboard/')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()} !')
            return redirect('/accounts/dashboard/')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Vous êtes déconnecté.')
    return redirect('/accounts/login/')

@login_required
def assign_role_view(request, user_id):
    if request.user.role != 'ADMIN':
        messages.error(request, 'Accès non autorisé.')
        return redirect('/accounts/dashboard/')
    
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = UserRoleForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Rôle de {user.get_full_name()} mis à jour.')
            return redirect('/admin/')
    else:
        form = UserRoleForm(instance=user)
    return render(request, 'accounts/assign_role.html', {'form': form, 'target_user': user})

@login_required
def dashboard(request):
    """Tableau de bord selon le rôle de l'utilisateur"""
    context = {
        'user': request.user,
        'role': request.user.role,
    }
    
    if request.user.role == 'ADMIN':
        context['total_employees'] = CustomUser.objects.filter(role='EMPLOYEE').count()
        context['total_managers'] = CustomUser.objects.filter(role='MANAGER').count()
        context['active_employees'] = CustomUser.objects.filter(status='ACTIVE').count()
    elif request.user.role == 'MANAGER':
        context['team_size'] = CustomUser.objects.filter(manager=request.user).count()
    
    return render(request, 'accounts/dashboard.html', context)


# ============ VUES POUR LA GESTION DES EMPLOYÉS ============

@login_required
@user_passes_test(is_admin)
def employee_list(request):
    """Liste des employés avec filtres (Admin RH seulement)"""
    employees = CustomUser.objects.all().order_by('first_name', 'last_name')
    
    # Filtres
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    department_filter = request.GET.get('department', '')
    search_query = request.GET.get('search', '')
    
    if role_filter:
        employees = employees.filter(role=role_filter)
    if status_filter:
        employees = employees.filter(status=status_filter)
    if department_filter:
        employees = employees.filter(department__icontains=department_filter)
    if search_query:
        employees = employees.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(employee_id__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(employees, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'employees': page_obj,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'department_filter': department_filter,
        'search_query': search_query,
        'total_count': employees.count(),
        'role_choices': CustomUser.ROLE_CHOICES,
        'status_choices': CustomUser.STATUS_CHOICES,
    }
    return render(request, 'accounts/employee_list.html', context)

@login_required
@user_passes_test(is_admin)
def employee_create(request):
    """Ajouter un nouvel employé (Admin RH seulement)"""
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            from django.utils.crypto import get_random_string
            temp_password = get_random_string(length=10)            
            user.set_password(temp_password)
            user.save()
            
            messages.success(request, f'Employé {user.get_full_name()} ajouté avec succès. Mot de passe temporaire: {temp_password}')
            return redirect('accounts:employee_list')
    else:
        form = EmployeeForm()
    
    return render(request, 'accounts/employee_form.html', {'form': form, 'title': 'Ajouter un employé'})

@login_required
@user_passes_test(is_admin)
def employee_edit(request, pk):
    """Modifier les informations d'un employé (Admin RH seulement)"""
    employee = get_object_or_404(CustomUser, id=pk)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f'Employé {employee.get_full_name()} modifié avec succès.')
            return redirect('accounts:employee_list')
    else:
        form = EmployeeForm(instance=employee)
    
    return render(request, 'accounts/employee_form.html', {'form': form, 'title': 'Modifier employé', 'employee': employee})

@login_required
@user_passes_test(is_admin)
def employee_deactivate(request, pk):
    """Désactiver un employé (Admin RH seulement)"""
    employee = get_object_or_404(CustomUser, id=pk)
    
    if request.method == 'POST':
        form = EmployeeStatusForm(request.POST, instance=employee)
        if form.is_valid():
            status = form.cleaned_data['status']
            employee.status = status
            
            if status in ['INACTIVE', 'TERMINATED']:
                employee.is_active = False
            else:
                employee.is_active = True
            
            employee.save()
            messages.success(request, f'Statut de {employee.get_full_name()} mis à jour: {employee.get_status_display_fr()}')
            return redirect('accounts:employee_list')
    else:
        form = EmployeeStatusForm(instance=employee)
    
    return render(request, 'accounts/employee_deactivate.html', {'form': form, 'employee': employee})

@login_required
@user_passes_test(is_admin)
def employee_detail(request, pk):
    """Consulter les détails d'un employé (Admin RH seulement)"""
    employee = get_object_or_404(CustomUser, id=pk)
    return render(request, 'accounts/employee_detail.html', {'employee': employee})

@login_required
@user_passes_test(is_manager_or_admin)
def my_team(request):
    """Voir les employés de mon équipe (Manager)"""
    if request.user.role == 'ADMIN':
        employees = CustomUser.objects.filter(role='EMPLOYEE').order_by('first_name', 'last_name')
    else:
        employees = CustomUser.objects.filter(manager=request.user).order_by('first_name', 'last_name')
    
    context = {
        'employees': employees,
        'is_manager': request.user.role == 'MANAGER',
    }
    return render(request, 'accounts/my_team.html', context)

@login_required
def my_profile(request):
    """Consulter mes informations (Employé)"""
    return render(request, 'accounts/my_profile.html', {'employee': request.user})




@login_required
@user_passes_test(is_admin)
def contract_create(request, employee_id):
    """Associer un contrat à un employé"""
    employee = get_object_or_404(CustomUser, id=employee_id)
    
    # Vérifier si l'employé a déjà un contrat
    existing_contract = Contract.objects.filter(employee=employee).first()
    
    if request.method == 'POST':
        form = ContractForm(request.POST, request.FILES)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.employee = employee
            contract.save()
            messages.success(request, f'Contrat ajouté pour {employee.get_full_name()}')
            return redirect('accounts:employee_detail', pk=employee.id)
    else:
        form = ContractForm()
    
    context = {
        'form': form,
        'employee': employee,
        'existing_contract': existing_contract,
    }
    return render(request, 'accounts/contract_form.html', context)

@login_required
@user_passes_test(is_admin)
def contract_edit(request, contract_id):
    """Modifier un contrat"""
    contract = get_object_or_404(Contract, id=contract_id)
    
    if request.method == 'POST':
        form = ContractForm(request.POST, request.FILES, instance=contract)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contrat modifié avec succès')
            return redirect('accounts:employee_detail', pk=contract.employee.id)
    else:
        form = ContractForm(instance=contract)
    
    return render(request, 'accounts/contract_form.html', {'form': form, 'contract': contract})

@login_required
@user_passes_test(is_admin)
def contract_detail(request, contract_id):
    """Voir les détails d'un contrat"""
    contract = get_object_or_404(Contract, id=contract_id)
    return render(request, 'accounts/contract_detail.html', {'contract': contract})