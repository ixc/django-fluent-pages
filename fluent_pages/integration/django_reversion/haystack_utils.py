from haystack.signals import RealtimeSignalProcessor


class ReversionRealtimeSignalProcessor(RealtimeSignalProcessor):
    """
    Customised Haystack realtime processor that works around problems
    processing django-fluent-page pages that have been reverted by
    django-reversion.
    """

    def handle_save(self, sender, instance, **kwargs):
        """
        Process save events as usual except for raw instances that contain
        django-parler translations, in which case we reload the instance from
        the DB to give the instance a chance to properly re-initialise its
        translated field relationships.
        
        This prevents Haystack from producing errors like the following when
        a page is reverted:

            parler.models.DoesNotExist: Page does not have a translation for the current language!
            Page ID #1, language=en-au
            Attempted to read attribute title.
        """
        if kwargs.get('raw', False) and hasattr(instance, '_parler_meta'):
            instance = instance.__class__.objects.get(pk=instance.pk)
            kwargs['raw'] = False

        return super(ReversionRealtimeSignalProcessor, self).handle_save(
            sender, instance, **kwargs)

