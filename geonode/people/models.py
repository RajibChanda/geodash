# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2016 OSGeo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################
#@jahangir091
import datetime
#end

from django.db import models
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.contrib.auth.models import AbstractUser, UserManager
from django.db.models import signals
from django.conf import settings

#@jahangir091
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core import validators
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, Http404
from geonode.settings import REMOVE_ANONYMOUS_USER
#end


from taggit.managers import TaggableManager

from geonode.base.enumerations import COUNTRIES
from geonode.groups.models import GroupProfile

from account.models import EmailAddress

#@jahangir091
from user_messages.models import UserThread
#end


from .utils import format_address

if 'notification' in settings.INSTALLED_APPS:
    from notification import models as notification


#@jahangir091
def get_anonymous_user():
    return get_user_model().objects.get(username = 'AnonymousUser')
#end


class ProfileUserManager(UserManager):
    def get_by_natural_key(self, username):
        return self.get(username__iexact=username)


class Profile(AbstractUser):

    """Fully featured Geonode user"""

    organization = models.CharField(
        _('Organization Name'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('name of the responsible organization'))
    profile = models.TextField(_('Profile'), null=True, blank=True, help_text=_('introduce yourself'))
    position = models.CharField(
        _('Position Name'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('role or position of the responsible person'))
    voice = models.CharField(_('Voice'), max_length=255, blank=True, null=True, help_text=_(
        'telephone number by which individuals can speak to the responsible organization or individual'))
    fax = models.CharField(_('Facsimile'), max_length=255, blank=True, null=True, help_text=_(
        'telephone number of a facsimile machine for the responsible organization or individual'))
    delivery = models.CharField(
        _('Delivery Point'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('physical and email address at which the organization or individual may be contacted'))
    city = models.CharField(
        _('City'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('city of the location'))
    area = models.CharField(
        _('Administrative Area'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('state, province of the location'))
    zipcode = models.CharField(
        _('Postal Code'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('ZIP or other postal code'))
    country = models.CharField(
        choices=COUNTRIES,
        max_length=3,
        blank=True,
        null=True,
        help_text=_('country of the physical address'))
    keywords = TaggableManager(_('keywords'), blank=True, help_text=_(
        'commonly used word(s) or formalised word(s) or phrase(s) used to describe the subject \
            (space or comma-separated'))
    #@jahangir091
    last_notification_view = models.DateTimeField(default=datetime.datetime.now)
    #end
    def get_absolute_url(self):
        return reverse('profile_detail', args=[self.username, ])

    def __unicode__(self):
        return u"%s" % (self.username)

    def class_name(value):
        return value.__class__.__name__

    objects = ProfileUserManager()
    USERNAME_FIELD = 'username'

    def group_list_public(self):
        return GroupProfile.objects.exclude(access="private").filter(groupmember__user=self)

    def group_list_all(self):
        return GroupProfile.objects.filter(groupmember__user=self)

    #@jahangir091
    def group_list_with_default_check(self):
        group_list = GroupProfile.objects.filter(groupmember__user=self)
        default_group = GroupProfile.objects.get(slug='default')
        if len(group_list) > 1 and default_group in group_list:
            return group_list.exclude(slug='default')
        else:
            return group_list

    @property
    def is_manager_of_any_group(self):
        return GroupProfile.objects.filter(groupmember__user=self, groupmember__role="manager").exists()

    @property
    def is_member_of_any_group(self):
        return GroupProfile.objects.filter(groupmember__user=self, groupmember__role="member").exists()

    @property
    def message_unread(self):
        return UserThread.objects.filter(user=self, unread=True).count()
    #end


    def keyword_list(self):
        """
        Returns a list of the Profile's keywords.
        """
        return [kw.name for kw in self.keywords.all()]

    @property
    def name_long(self):
        if self.first_name and self.last_name:
            return '%s %s (%s)' % (self.first_name, self.last_name, self.username)
        elif (not self.first_name) and self.last_name:
            return '%s (%s)' % (self.last_name, self.username)
        elif self.first_name and (not self.last_name):
            return '%s (%s)' % (self.first_name, self.username)
        else:
            return self.username

    @property
    def location(self):
        return format_address(self.delivery, self.zipcode, self.city, self.area, self.country)


    #@jahangir091
    @property
    def notification_count(self):
        return self.notifications.filter(read=False, deleted=False, created__gt=self.last_notification_view).count()
    #end


def get_anonymous_user_instance(Profile):
    return Profile(pk=-1, username='AnonymousUser')


def profile_post_save(instance, sender, **kwargs):
    """
    Make sure the user belongs by default to the anonymous group.
    This will make sure that anonymous permissions will be granted to the new users.
    """
    from django.contrib.auth.models import Group
    anon_group, created = Group.objects.get_or_create(name='anonymous')
    instance.groups.add(anon_group)
    # keep in sync Profile email address with Account email address
    if instance.email not in [u'', '', None] and not kwargs.get('raw', False):
        address, created = EmailAddress.objects.get_or_create(
            user=instance, primary=True,
            defaults={'email': instance.email, 'verified': False})
        if not created:
            EmailAddress.objects.filter(user=instance, primary=True).update(email=instance.email)


    #@jahangir091
    default_group, created_group = GroupProfile.objects.get_or_create(slug='default')
    if not default_group.title:
        default_group.title = 'default organization'
        default_group.save()
    if instance != get_anonymous_user():
        if instance.is_superuser:
            default_group.join(instance, role='manager')
        else:
            default_group.join(instance, role='member')
    #end



def email_post_save(instance, sender, **kw):
    if instance.primary:
        Profile.objects.filter(id=instance.user.pk).update(email=instance.email)


def profile_pre_save(instance, sender, **kw):
    matching_profiles = Profile.objects.filter(id=instance.id)
    if matching_profiles.count() == 0:
        return
    if instance.is_active and not matching_profiles.get().is_active and \
            'notification' in settings.INSTALLED_APPS:
        notification.send([instance, ], "account_active")


#@jahangir091
def profile_pre_delete(instance, sender, **kw):
    if instance == get_anonymous_user() and REMOVE_ANONYMOUS_USER == False:
        # raise PermissionDenied
        raise Http404('Please dont try to delete "Anonymous User". This may break the system.')
#end



signals.pre_save.connect(profile_pre_save, sender=Profile)
signals.post_save.connect(profile_post_save, sender=Profile)
signals.post_save.connect(email_post_save, sender=EmailAddress)


#@jahangir091
signals.pre_delete.connect(profile_pre_delete, sender=Profile)
#end