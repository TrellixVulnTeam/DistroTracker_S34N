# Copyright 2013 The Debian Package Tracking System Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/ptsauthors
#
# This file is part of the Package Tracking System. It is subject to the
# license terms in the LICENSE file found in the top-level directory of
# this distribution and at http://deb.li/ptslicense. No part of the Package
# Tracking System, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE file.

"""
Tests for the ``vendor`` app.

The test suite automatically includes any tests available in a ``tests``
module of all subpackages.
"""

from __future__ import unicode_literals
from django.test import TestCase
from django.test.utils import override_settings
from django.core import mail
from pts.dispatch.tests import DispatchTestHelperMixin
from pts.core.models import Package
import sys
import inspect
import importlib


def get_subpackages():
    """
    Helper function returns all subpackages of the ``vendor`` package.
    """
    import pkgutil

    current_module = sys.modules[__name__]
    current_package = sys.modules[current_module.__package__]

    return [
        name
        for _, name, is_pkg in pkgutil.iter_modules(current_package.__path__)
        if is_pkg
    ]


def get_test_cases(tests_module):
    """
    Returns a list of all TestCase subclasses from the given module.
    """
    module_name = tests_module.__name__
    return [
        klass
        for _, klass in inspect.getmembers(tests_module, inspect.isclass)
        if issubclass(klass, TestCase) and klass.__module__ == module_name
    ]


def suite():
    """
    Loads tests found in all subpackages of the ``pts.vendor`` package.
    """
    import unittest
    suite = unittest.TestSuite()

    subpackages = get_subpackages()

    # Build a list of all possible tests modules in the subpackages.
    tests_modules = [
        '..' + subpackage + '.tests'
        for subpackage in subpackages
    ]
    # Add this tests module to the list too
    tests_modules.append('..tests')

    # Try importing the tests from all TestCase classes defined in the
    # found tests modules.
    for tests_module_name in tests_modules:
        try:
            tests_module = importlib.import_module(tests_module_name, __name__)
        except ImportError:
            # The subpackage does not have a tests module.
            continue

        # Following convention, first try using a suite() function in the
        # module.
        if hasattr(tests_module, 'suite') and tests_module.__name__ != __name__:
            suite.addTest(getattr(tests_module, 'suite')())
        else:
            # Just add all TestCase subclasses.
            for test_case in get_test_cases(tests_module):
                all_tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
                suite.addTest(all_tests)

    return suite


@override_settings(PTS_VENDOR_RULES='pts.vendor.debian.rules')
class DispatchDebianSpecificTest(TestCase, DispatchTestHelperMixin):
    """
    Tests Debian-specific keyword classification.
    """
    def setUp(self):
        self.clear_message()
        self.from_email = 'dummy-email@domain.com'
        self.set_package_name('dummy-package')
        self.add_header('From', 'Real Name <{from_email}>'.format(
            from_email=self.from_email))
        self.add_header('Subject', 'Some subject')
        self.set_message_content('message content')

        self.package = Package.objects.create(name=self.package_name)

    def test_dispatch_bts_control(self):
        """
        Tests that the dispatch properly tags a message as bts-control
        """
        self.set_header('X-Debian-PR-Message', 'transcript of something')
        self.set_header('X-Loop', 'owner@bugs.debian.org')
        self.subscribe_user_with_keyword('user@domain.com', 'bts-control')

        self.run_dispatch()

        self.assert_message_forwarded_to('user@domain.com')
        self.assert_header_equal('X-PTS-Keyword', 'bts-control')

    def test_dispatch_bts(self):
        """
        Tests that the dispatch properly tags a message as bts
        """
        self.set_header('X-Debian-PR-Message', '1')
        self.set_header('X-Loop', 'owner@bugs.debian.org')
        self.subscribe_user_with_keyword('user@domain.com', 'bts')

        self.run_dispatch()

        self.assert_message_forwarded_to('user@domain.com')
        self.assert_header_equal('X-PTS-Keyword', 'bts')

    def test_dispatch_upload_source(self):
        self.set_header('Subject', 'Accepted 0.1 in unstable')
        self.set_header('X-DAK', 'DAK')
        self.add_header('From', 'Real Name <{from_email}>'.format(
            from_email=self.from_email))
        self.set_message_content('Files\nchecksum lib.dsc\ncheck lib2.dsc')
        self.subscribe_user_with_keyword('user@domain.com', 'upload-source')

        self.run_dispatch()

        self.assert_message_forwarded_to('user@domain.com')
        self.assert_header_equal('X-PTS-Keyword', 'upload-source')

    def test_dispatch_upload_binary(self):
        self.set_header('Subject', 'Accepted 0.1 in unstable')
        self.set_header('X-DAK', 'DAK')
        self.add_header('From', 'Real Name <{from_email}>'.format(
            from_email=self.from_email))
        self.set_message_content('afgdfgdrterfg')
        self.subscribe_user_with_keyword('user@domain.com', 'upload-binary')

        self.run_dispatch()

        self.assert_message_forwarded_to('user@domain.com')
        self.assert_header_equal('X-PTS-Keyword', 'upload-binary')

    def test_dispatch_archive(self):
        self.set_header('Subject', 'Comments regarding some changes')
        self.set_header('X-DAK', 'DAK')
        self.add_header('From', 'Real Name <{from_email}>'.format(
            from_email=self.from_email))
        self.set_message_content('afgdfgdrterfg')
        self.subscribe_user_with_keyword('user@domain.com', 'archive')

        self.run_dispatch()

        self.assert_message_forwarded_to('user@domain.com')
        self.assert_header_equal('X-PTS-Keyword', 'archive')

    def test_default_not_trusted(self):
        """
        Tests that a non-trusted default message is dropped.
        """
        self.subscribe_user_to_package('user@domain.com', self.package_name)

        self.run_dispatch()

        self.assertEqual(len(mail.outbox), 0)

    def test_debian_trusts_mozilla(self):
        """
        Tests that messages tagged with the default keyword are forwarded when
        they originated from Bugzilla.
        """
        self.set_header('X-Bugzilla-Product', '1')
        self.subscribe_user_to_package('user@domain.com', self.package_name)

        self.run_dispatch()

        self.assertEqual(len(mail.outbox), 1)

    def test_debian_specific_headers(self):
        """
        Tests that debian specific headers are included in forwarded messages.
        """
        expected_headers = [
            ('X-Debian-Package', self.package_name),
            ('X-Debian', 'PTS'),
        ]
        self.subscribe_user_to_package('user@domain.com', self.package_name)

        self.run_dispatch()

        self.assert_all_headers_found(expected_headers)
