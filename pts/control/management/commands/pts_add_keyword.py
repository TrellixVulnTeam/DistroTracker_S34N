# Copyright 2013 The Debian Package Tracking System Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/ptsauthors
#
# This file is part of the Package Tracking System. It is subject to the
# license terms in the LICENSE file found in the top-level directory of
# this distribution and at http://deb.li/ptslicense. No part of the Package
# Tracking System, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE file.

from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pts.core.models import Keyword, EmailUser, Subscription
from pts.core.utils import get_or_none


class Command(BaseCommand):
    """
    A management command that adds a new keyword.

    It supports simply adding a new keyword and allowing users to add it to
    their subscriptions or to automatically add it to users' lists that
    already contain a different keyword (given as a parameter to the command).
    """
    args = 'keyword [existing-keyword]'

    help = ("Add a new keyword.\n."
            "The command supports simply adding a new keyword and allowing"
            " users to add it to their subscriptions or to automatically add"
            " it to users' lists that already contain a different keyword"
            " (given as a parameter to the command).")

    def warn(self, text):
        if self.verbose > 1:
            self.stdout.write("Warning: {text}".format(text=text))

    def add_keyword_to_user_defaults(self, keyword, user_set):
        """
        Adds the given keyword to the default_keywords list of each user found
        in the given QuerySet user_set.
        """
        for user in user_set:
            user.default_keywords.add(keyword)

    def add_keyword_to_subscriptions(self, new_keyword, existing_keyword):
        existing_keyword = get_or_none(Keyword, name=existing_keyword)
        if not existing_keyword:
            raise CommandError("Given keyword does not exist. No actions taken.")

        self.add_keyword_to_user_defaults(
            new_keyword,
            EmailUser.objects.filter(default_keywords=existing_keyword)
        )
        for subscription in Subscription.objects.all():
            if existing_keyword in subscription.keywords.all():
                if subscription._use_user_default_keywords:
                    # Skip these subscriptions since the keyword was already
                    # added to user's default lists.
                    continue
                else:
                    subscription.keywords.add(new_keyword)

    @transaction.commit_on_success
    def handle(self, *args, **kwargs):
        self.verbose = int(kwargs.get('verbosity', 1)) > 1
        if len(args) < 1:
            raise CommandError("The name of the new keyword must be given")
        keyword = args[0]

        keyword, created = Keyword.objects.get_or_create(name=keyword)

        if not created:
            self.warn("The given keyword already exists")
            return

        if len(args) > 1:
            # Add the new keyword to all subscribers and subscriptions which
            # contain the parameter keyword
            other_keyword = args[1]
            self.add_keyword_to_subscriptions(keyword, other_keyword)

        if self.verbose:
            self.stdout.write('Successfully added new keyword {keyword}'.format(
                keyword=keyword))