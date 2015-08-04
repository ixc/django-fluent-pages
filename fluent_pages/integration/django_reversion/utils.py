import reversion

from parler.models import ParlerOptions
from parler import cache

from django.db.models.signals import post_save


class FluentVersionAdapter(reversion.VersionAdapter):
    """
    django-reversion versioning adapter that checks if a model contains
    important known relationship fields that should be included in object
    versions, and if so automatically adds them to the `follow` list used
    internally when saving page versions.

    Also includes hooks to do extra work when necessary, such as refreshing the
    cache of django-parler translations used for django-fluent-pages'
    translated fields.
    """

    # Object fields to "follow" (traverse) when serializing version data, but
    # only if they are present in the object. These are important field names
    # for django-fluent-pages and django-fluent-content.
    follow_if_present = (
        'urlnode_ptr',  # Pointer to UrlNode proxy model from page
        'contentitem_set',  # ContentItem's associated with a page
        'contentitem_ptr',  # Pointer to ContentItem proxy model for items
        'placeholder',  # Placeholder for content items
        '_parler_meta',  # django-parler meta data for translated fields

        # Built-in support for external libraries
        'publisher_linked',  # django-model-publisher 1-to-1 to published page
    )

    def __init__(self, model):
        super(FluentVersionAdapter, self).__init__(model)

        # Convert follow tuple to set before we add our items to avoid dupes
        follow_set = set(self.follow)

        for attr_name in self.follow_if_present:
            if not hasattr(model, attr_name):
                continue

            # Special handling of django-parler meta data
            attr_value = getattr(model, attr_name)
            if isinstance(attr_value, ParlerOptions):
                # There may be multiple django-parler translations
                for parler_meta in attr_value:
                    follow_set.add(parler_meta.rel_name)

                    # Based on https://github.com/aldryn/aldryn-reversion :
                    # And make sure that when we revert them, we update the
                    # translations cache (this is normally done in the
                    # translation `save_base` method, but isn't called when
                    # reverting changes).
                    post_save.connect(
                        self._update_cache,
                        sender=parler_meta.model,
                        dispatch_uid='FluentVersionAdapter._update_cache.%s'
                                     % parler_meta.rel_name)
            # If model has named attribute, follow it
            else:
                follow_set.add(attr_name)

        # Replace class variable with updated relationship names to follow
        self.follow = follow_set

    def _update_cache(self, sender, instance, raw, **kwargs):
        """Update the translations cache when restoring from a revision."""
        if raw:
            # Raw is set to true (only) when restoring from fixtures or,
            # django-reversion
            cache._cache_translation(instance)
