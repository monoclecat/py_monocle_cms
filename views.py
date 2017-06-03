from django.shortcuts import get_object_or_404, render, redirect, render_to_response
from django.http import HttpResponseRedirect, HttpRequest, Http404
from django.urls import reverse
from django.views.generic.list import ListView
from django.views.generic import DetailView
from django.views.generic.edit import FormView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin

import markdown


import logging

from .md_extensions import *
from .models import Page, Content, Image
from .forms import PageEditForm, ImageUploadForm


def get_featured_and_other(language, user_is_admin=False):
    featured_projects = []
    other_projects = []

    if user_is_admin:
        perm_filtered_query = Page.objects.all()
    else:
        perm_filtered_query = Page.objects.all().exclude(admin_only=True)

    for page in perm_filtered_query.filter(featured=True):
        content = page.content.get(language=language)
        featured_projects.append([page.pk, content.name])
    for page in perm_filtered_query.filter(featured=False):
        content = page.content.get(language=language)
        other_projects.append([page.pk, content.name])

    return [featured_projects, other_projects]


class IndexView(ListView):
    pass


def login_view(request):
    if request.method == 'POST' and 'login' in request.POST:
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
        return HttpResponseRedirect(request.POST['next'])
    elif request.method == 'POST' and 'logout' in request.POST:
        logout(request)
        return HttpResponseRedirect(request.POST['next'])
    else:
        return render(request, 'monocle_cms/login_page.html', {'next': request.GET.get('next', '/login/')})


class ImageUploadView(FormView):
    form_class = ImageUploadForm
    template_name = 'monocle_cms/image_upload.html'
    success_url = '/image-upload'

    def get_context_data(self, **kwargs):
        context = super(ImageUploadView, self).get_context_data(**kwargs)
        images = Image.objects.all()
        context['images'] = images
        return context

    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        files = request.FILES.getlist('image_file_field')
        if form.is_valid():
            for f in files:
                Image.objects.create(file=f, tag=request.POST['tag'])
            return self.form_valid(form)
        else:
            return self.form_invalid(form)


class ContentView(DetailView):
    model = Page
    template_name = 'monocle_cms/page.html'
    context_object_name = 'page'

    def get_object(self, queryset=None):
        page = super(ContentView, self).get_object()
        if page.admin_only and not self.request.user.is_superuser:
            raise Http404
        return page

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(ContentView, self).get_context_data(**kwargs)

        context['content'], self.kwargs['language'] = context['page'].get_content(self.kwargs['language'])
        context['featured_projects'] = []
        context['other_projects'] = []
        context['language'] = self.kwargs['language']

        if self.kwargs['language'] is not None:
            context['featured_projects'], context['other_projects'] = get_featured_and_other(self.kwargs['language'],
                                                                                             self.request.user.is_superuser)

        return context

    def get(self, request, *args, **kwargs):
        if self.kwargs['language'] not in Page.languages:
            raise Http404

        if 'slug' not in self.kwargs:
            self.kwargs['slug'] = ''

        self.object = self.get_object()
        context = self.get_context_data(object=self.object)

        if context['content'] is None or self.kwargs['slug'] != context['content'].slug():
            # No content was found under the given language or slug was wrong
            return redirect(context['page'].get_absolute_url(self.kwargs['language']))

        md = markdown.Markdown(extensions=[PageBuildingExtensions()])
        context['content'].body = md.convert(context['content'].body)

        return self.render_to_response(context)


class ContentEditView(LoginRequiredMixin, FormView, ContentView):
    form_class = PageEditForm
    template_name = 'monocle_cms/page_edit.html'
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        if self.kwargs['language'] not in Page.languages:
            raise Http404

        self.object = self.get_object()
        context = ContentView.get_context_data(self, object=self.object)

        if context['page'] is not None and context['content'] is not None:
            self.initial = {'tag': context['page'].tag, 'created': context['page'].created,
                            'admin_only': context['page'].admin_only,
                            'featured': context['page'].featured, 'primary_image': context['page'].primary_image,
                            'other_images': context['page'].other_images, 'name': context['content'].name,
                            'headline': context['content'].headline, 'abstract': context['content'].abstract,
                            'body': context['content'].body}

        context = {**context, **FormView.get_context_data(self, **kwargs)}

        if context['content'] is None:
            if self.kwargs['slug'] != context['content'].slug():
                # No content was found under the given language or slug was wrong
                return redirect(context['page'].get_absolute_url(self.kwargs['language'], True))

        md = markdown.Markdown(extensions=[PageBuildingExtensions()])
        context['html_content_body'] = md.convert(context['content'].body)

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            page = Page.objects.get(pk=self.kwargs['pk'])
            form = PageEditForm(request.POST, instance=page)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save()

        content = self.object.content.get(language=self.kwargs['language'])

        content.name = self.request.POST['name']
        content.headline = self.request.POST['headline']
        content.abstract = self.request.POST['abstract']
        content.body = self.request.POST['body']
        content.save()

        self.success_url = self.object.get_absolute_url(self.kwargs['language'], True)
        return super(ContentEditView, self).form_valid(form)


class AdminView(LoginRequiredMixin, ListView):
    model = Page
    template_name = 'monocle_cms/admin.html'
    context_object_name = 'page'
    login_url = '/login/'

    def get_queryset(self):
        return Page.objects.all().order_by('-created')

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(AdminView, self).get_context_data(**kwargs)
        return context

    def post(self, request, *args, **kwargs):
        Page.objects.create()
        return HttpResponseRedirect(self.request.POST['next'])