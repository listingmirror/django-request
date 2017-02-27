# -*- coding: utf-8 -*-
import json
from datetime import date, timedelta
from functools import update_wrapper

from django.conf.urls import url
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _

from . import settings
from .models import Request
from .plugins import plugins
from .traffic import modules


class RequestAdmin(admin.ModelAdmin):
    list_display = ('time', 'path', 'response', 'method', 'request_from')
    fieldsets = (
        (_('Request'), {
            'fields': ('method', 'path', 'time', 'is_secure', 'is_ajax')
        }),
        (_('Response'), {
            'fields': ('response',)
        }),
        (_('User info'), {
            'fields': ('referer', 'user_agent', 'ip', 'user', 'language')
        })
    )
    raw_id_fields = ('user',)
    readonly_fields = ('time',)

    def lookup_allowed(self, key, value):
        request_lookup_field = 'user__{0}'.format(settings.USER_FIELD)
        return key == request_lookup_field or super(RequestAdmin, self).lookup_allowed(key, value)

    def request_from(self, obj):
        if obj.user_id:
            user_field = settings.USER_FIELD
            user = obj.get_user()
            return '<a href="?user__{0}={1}" title="{2}">{3}</a>'.format(
                user_field,
                getattr(user, user_field),
                _('Show only requests from this user.'),
                user,
            )
        return '<a href="?ip={0}" title="{1}">{0}</a>'.format(
            obj.ip,
            _('Show only requests from this IP address.'),
        )
    request_from.short_description = 'From'
    request_from.allow_tags = True

    def get_urls(self):
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = (self.model._meta.app_label, self.model._meta.model_name)
        return [
            url(r'^overview/$', wrap(self.overview), name='{0}_{1}_overview'.format(*info)),
            url(r'^overview/traffic/$', wrap(self.traffic), name='{0}_{1}_traffic'.format(*info)),
        ] + super(RequestAdmin, self).get_urls()

    def overview(self, request):
        qs = Request.objects.this_month()
        for plugin in plugins.plugins:
            plugin.qs = qs

        return render(
            request,
            'admin/request/request/overview.html',
            {
                'title': _('Request overview'),
                'plugins': plugins.plugins,
            }
        )

    def traffic(self, request):
        try:
            days_count = int(request.GET.get('days', 30))
        except ValueError:
            days_count = 30

        if days_count < 10:
            days_step = 1
        elif days_count < 60:
            days_step = 2
        else:
            days_step = 30

        days = [date.today() - timedelta(day) for day in range(0, days_count, days_step)]
        days_qs = [(day, Request.objects.day(date=day)) for day in days]
        return HttpResponse(json.dumps(modules.graph(days_qs)), content_type='text/javascript')


admin.site.register(Request, RequestAdmin)
