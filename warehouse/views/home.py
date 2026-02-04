from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    """
    View-диспетчер: перенаправляє користувача на відповідний дашборд залежно від ролі.
    Використовується як LOGIN_REDIRECT_URL.
    """
    # Якщо менеджер або адмін (is_staff) - на дашборд менеджера
    if request.user.is_staff:
        return redirect('manager_dashboard')
    
    # Інакше (прораб/звичайний користувач) - на основний дашборд (index)
    # index - це view general.index, який вже містить логіку для прораба
    return redirect('index')