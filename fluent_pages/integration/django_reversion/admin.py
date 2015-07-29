from django.conf.urls import patterns, url

from reversion.admin import VersionAdmin

from fluent_pages.integration.fluent_contents import admin as fc_admin
from fluent_pages.pagetypes.fluentpage.admin import FluentPageAdmin
from fluent_pages.pagetypes.flatpage.admin import FlatPageAdmin
from fluent_contents.models import ContentItem, Placeholder
from fluent_contents.extensions import plugin_pool

from .utils import FluentVersionAdapter


class BaseFluentVersionAdmin(VersionAdmin):
    """
    Base class for customizing django-reversion's VersionAdmin for Fluent
    page types.
    """

    # Override VersionAdmin._autoregister with customisations to:
    # * register django-parler translation fields and follow relationships
    # * register ContentItems exposed as plugins
    # * register Placeholder
    def _autoregister(self, model, follow=None):
        # Skip pre-registered models
        if not self.revision_manager.is_registered(model):
            follow = follow or []
            # Use model_meta.concrete_model to catch proxy models
            for parent_cls, field in \
                    model._meta.concrete_model._meta.parents.items():
                follow.append(field.name)
                self._autoregister(parent_cls)
            # Process django-parler translations, if any
            if hasattr(model, '_parler_meta'):
                for parler_meta in model._parler_meta:
                    follow.append(parler_meta.rel_name)
                    self._autoregister(parler_meta.model)
            print "Registering %r following=%r" % (model, follow)
            self.revision_manager.register(model, follow=follow,
                                           format=self.reversion_format,
                                           adapter_cls=FluentVersionAdapter)
        # Register all ContentItem models registered as plugin
        if not issubclass(model, ContentItem):
            for content_item_model in plugin_pool.get_model_classes():
                if not self.revision_manager.is_registered(content_item_model):
                    self._autoregister(content_item_model)
            # Register Placeholder
            if not self.revision_manager.is_registered(Placeholder):
                self._autoregister(Placeholder)

    # Override VersionAdmin get_urls to return extra fake-ish URLs necessary
    # to support url reversal for "parent"-specific URL paths through this
    # admin which operates in context of a "child" admin.
    def get_urls(self):
        urls = super(BaseFluentVersionAdmin, self).get_urls()

        # Hack to also register alternate 'fluent_pages_page_XYZ' URL names to
        # work with URL lookups on history/recovery pages from *parent* admin
        # class, since this polymorphic admin generates
        # 'fluentpage_fluentpage_XYZ' URL names instead.
        # TODO Can we avoid this hack somehow?
        admin_site = self.admin_site
        reversion_urls = patterns(
            "",
            url("^recover/$",
                admin_site.admin_view(self.recoverlist_view),
                name='fluent_pages_page_recoverlist'),
            url("^recover/([^/]+)/$",
                admin_site.admin_view(self.recover_view),
                name='fluent_pages_page_recover'),
            url("^([^/]+)/history/([^/]+)/$",
                admin_site.admin_view(self.revision_view),
                name='fluent_pages_page_revision'),
        )
        return reversion_urls + urls

    def revisionform_view(self, request, version, template_name,
                          extra_context=None):
        """
        Override handling of reversion's revert-with-delete to instead delete
        entire object. We must do this to clean up obsolete relationships
        rather than relying on django-reversion's `delete=True` flag to
        `version.revision.revert()` which does not properly handle the unusual
        polymorphic content type IDs assigned to MarkupItem variants.
        """
        def hack_revision_revert(delete=True):
            obj = version.object
            if obj:
                obj.delete()
            version.revision._original_revert()
        version.revision._original_revert = version.revision.revert
        version.revision.revert = hack_revision_revert

        return super(BaseFluentVersionAdmin, self).revisionform_view(
            request, version, template_name, extra_context=extra_context)


class ReversionFlatPageAdmin(BaseFluentVersionAdmin, FlatPageAdmin):

    revision_form_template = 'admin/fluent_pages/pagetypes/flatpage/reversion/revision_form.html'
    recover_form_template = 'admin/fluent_pages/pagetypes/flatpage/reversion/recover_form.html'


class ReversionFluentContentsPageAdmin(BaseFluentVersionAdmin,
                                       fc_admin.FluentContentsPageAdmin):

    revision_form_template = 'admin/fluentpage/reversion/revision_form.html'
    recover_form_template = 'admin/fluentpage/reversion/recover_form.html'

    #: The default template name, which is available in the template context.
    #: Use ``{% extend base_change_form_template %}`` in templates to inherit from it.
    base_change_form_template = "admin/fluent_pages/page/base_change_form.html"


class ReversionFluentPageAdmin(ReversionFluentContentsPageAdmin,
                               FluentPageAdmin):
    pass
