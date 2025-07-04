from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin

from .forms import PasswordChangeForm, ForcePasswordChangeForm
from .models import PasswordReset


class PasswordChangeView(LoginRequiredMixin, DjangoPasswordChangeView):
    """Allow logged-in users to change their password"""
    form_class = PasswordChangeForm
    template_name = 'users/password_change.html'
    
    def get_success_url(self):
        # Redirect back to profile if user has organization
        if self.request.user.organization:
            return reverse('organizations:profile', kwargs={'pk': self.request.user.organization.pk})
        return reverse('organizations:dashboard')
    
    def form_valid(self, form):
        # Update password_changed_at timestamp
        user = form.save()
        user.password_changed_at = timezone.now()
        user.must_change_password = False
        user.save(update_fields=['password_changed_at', 'must_change_password'])
        
        # Mark any active password resets as inactive
        PasswordReset.objects.filter(
            user=self.request.user,
            is_active=True
        ).update(is_active=False, used_at=timezone.now())
        
        # Clear password reset popup session flag
        self.request.session.pop('show_password_reset_popup', None)
        
        # IMPORTANT: Update session auth hash to keep user logged in
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(self.request, user)
        
        messages.success(self.request, 'Your password has been changed successfully!')
        return super().form_valid(form)


class ForcePasswordChangeView(LoginRequiredMixin, FormView):
    """Force users to change password after admin reset"""
    form_class = ForcePasswordChangeForm
    template_name = 'users/force_password_change.html'
    
    def get_success_url(self):
        # Redirect back to profile if user has organization
        if self.request.user.organization:
            return reverse('organizations:profile', kwargs={'pk': self.request.user.organization.pk})
        return reverse('organizations:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        # Only accessible if user must change password
        if not request.user.must_change_password:
            return redirect('organizations:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Save the new password
        user = form.save()
        
        # Mark any active password resets as inactive and used
        PasswordReset.objects.filter(
            user=self.request.user,
            is_active=True
        ).update(is_active=False, used_at=timezone.now())
        
        # Update password changed timestamp
        self.request.user.password_changed_at = timezone.now()
        self.request.user.save(update_fields=['password_changed_at'])
        
        # Clear password reset popup session flag
        self.request.session.pop('show_password_reset_popup', None)
        
        # IMPORTANT: Update session auth hash to keep user logged in
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(self.request, user)
        
        messages.success(self.request, 'Your password has been changed successfully!')
        return super().form_valid(form)


@login_required
def password_change_redirect(request):
    """Redirect to appropriate password change view"""
    if request.user.must_change_password:
        return redirect('users:force_password_change')
    else:
        return redirect('users:password_change')