# NOTE: This module exists for Fluent admin mixins because you cannot import
# FluentPageAdmin etc implementations in a module that also contains mixins
from reversion.admin import VersionAdmin

from django.conf.urls import patterns, url


class ReversionParentAdminMixin(VersionAdmin):
    """
    Parent admin mixin with support for versioning, applies reversion features
    when we are working in a "parent" admin context, which is anywhere
    django-fluent-pages cannot identify the exact page type of the item we are
    working on.
    """

    @property
    def change_list_template(self):
        # Prevent reversion from overriding the change_list template with its
        # own if there are other classes in the MRO that want precedence. Note
        # how super() is called on VersionAdmin, and not this class.
        templates = super(VersionAdmin, self).change_list_template
        if isinstance(templates, basestring):
            templates = [templates]
        templates.insert(-1, 'reversion/change_list.html')
        return templates

    recover_list_template = \
        'admin/fluent_pages/integration/django_reversion/recover_list.html'

    def get_urls(self):
        """
        Override VersionAdmin.get_urls to return only the URL mappings that
        make sense for a "parent" admin context, namely only listing URLs.
        """
        # Avoid VersionAdmin.get_urls, go to its superclass instead
        urls = super(VersionAdmin, self).get_urls()
        admin_site = self.admin_site
        opts = self.model._meta
        info = opts.app_label, opts.model_name,
        reversion_urls = patterns(
            "",
            url("^recover/$",
                admin_site.admin_view(self.recoverlist_view),
                name='%s_%s_recoverlist' % info),
        )
        return reversion_urls + urls
