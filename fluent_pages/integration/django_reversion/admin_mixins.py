# NOTE: This module exists for Fluent admin mixins because you cannot import
# FluentPageAdmin etc implementations in a module that also contains mixins
from reversion.admin import VersionAdmin

from django.conf.urls import patterns, url


class FluentReversionAdminMixin(VersionAdmin):
    """
    Admin for use as mixin via settings.FLUENT_PAGES_PARENT_ADMIN_MIXIN to
    apply reversion features when we are working in a "parent" admin context,
    which is anywhere django-fluent-pages cannot identify the exact page type
    of the item we are working on.
    """

    def get_urls(self):
        """
        Override VersionAdmin.get_urls to return only the URL mappings that
        make sense for a "parent" admin context, namely only listing URLs.
        """
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
