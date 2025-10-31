from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView


class LoginPageView(TemplateView):
    template_name = 'frontend/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(reverse_lazy('frontend:main'))
        return super().dispatch(request, *args, **kwargs)


class MainPageView(LoginRequiredMixin, TemplateView):
    template_name = 'frontend/main.html'
    login_url = reverse_lazy('frontend:login')


class ProcessingPageView(LoginRequiredMixin, TemplateView):
    template_name = 'frontend/processing.html'
    login_url = reverse_lazy('frontend:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['conversion_id'] = self.kwargs.get('conversion_id')
        return context


class GalleryPageView(LoginRequiredMixin, TemplateView):
    template_name = 'frontend/gallery.html'
    login_url = reverse_lazy('frontend:login')
