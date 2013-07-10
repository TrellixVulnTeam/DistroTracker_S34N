# -*- coding: utf-8 -*-

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
Tests for the PTS core views.
"""
from __future__ import unicode_literals
from django.test import TestCase
from pts.core.models import Package, BinaryPackage
from pts.core.models import SourcePackage
from pts.core.models import PseudoPackage
import json

from django.core.urlresolvers import reverse


class PackageViewTest(TestCase):
    """
    Tests for the package view.
    """
    def setUp(self):
        self.package = SourcePackage.objects.create(name='dummy-package')
        self.binary_package = BinaryPackage.objects.create(
            name='binary-package', source_package=self.package)
        self.pseudo_package = PseudoPackage.objects.create(name='pseudo-pkg')

    def get_package_url(self, package_name):
        """
        Helper method which returns the URL for the package with the given name
        """
        return reverse('pts-package-page', kwargs={
            'package_name': package_name
        })

    def test_source_package_page(self):
        """
        Tests that when visiting the package page for an existing package, a
        response based on the correct template is returned.
        """
        url = self.get_package_url(self.package.name)
        response = self.client.get(url)

        self.assertTemplateUsed(response, 'core/package.html')

    def test_binary_package_redirects_to_source(self):
        """
        Tests that when visited a binary package URL, the user is redirected
        to the corresponding source package page.
        """
        url = self.get_package_url(self.binary_package.name)
        response = self.client.get(url)

        self.assertRedirects(response, self.get_package_url(self.package.name))

    def test_pseudo_package_page(self):
        """
        Tests that when visiting a page for a pseudo package the correct
        template is used.
        """
        url = self.get_package_url(self.pseudo_package.name)
        response = self.client.get(url)

        self.assertTemplateUsed(response, 'core/package.html')

    def test_non_existent_package(self):
        """
        Tests that a 404 is returned when the given package does not exist.
        """
        url = self.get_package_url('no-exist')
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_subscriptions_only_package(self):
        """
        Tests that a 404 is returned when the given package is a "subscriptions
        only" package.
        """
        package_name = 'sub-only-pkg'
        # Make sure the package actually exists.
        Package.subscription_only_packages.create(name=package_name)

        url = self.get_package_url(package_name)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_legacy_url_redirects(self):
        """
        Tests that the old PTS style package URLs are correctly redirected.
        """
        url_template = '/{hash}/{package}.html'

        # Redirects for packages that do not start with "lib"
        url = url_template.format(hash=self.package.name[0],
                                  package=self.package.name)
        response = self.client.get(url)
        self.assertRedirects(response, self.get_package_url(self.package.name),
                             status_code=301)

        # No redirect when the hash does not match the package
        url = url_template.format(hash='q', package=self.package.name)
        self.assertEqual(self.client.get(url).status_code, 404)

        # Redirect when the package name starts with "lib"
        lib_package = 'libpackage'
        SourcePackage.objects.create(name=lib_package)
        url = url_template.format(hash='libp', package=lib_package)
        self.assertRedirects(self.client.get(url),
                             self.get_package_url(lib_package),
                             status_code=301)


class PackageSearchViewTest(TestCase):
    def setUp(self):
        self.pseudo_package = PseudoPackage.objects.create(name='pseudo-package')
        self.source_package = SourcePackage.objects.create(name='dummy-package')
        self.binary_package = BinaryPackage.objects.create(
            name='binary-package',
            source_package=self.source_package)

    def test_package_search_source_package(self):
        """
        Tests the package search when the given package is an existing source
        package.
        """
        response = self.client.get(reverse('pts-package-search'), {
            'package_name': self.source_package.name
        })

        self.assertRedirects(response, self.source_package.get_absolute_url())

    def test_package_search_pseudo_package(self):
        """
        Tests the package search when the given package is an existing pseudo
        package.
        """
        response = self.client.get(reverse('pts-package-search'), {
            'package_name': self.pseudo_package.name
        })

        self.assertRedirects(response, self.pseudo_package.get_absolute_url())

    def test_package_search_binary_package(self):
        """
        Tests the package search when the given package is an existing binary
        package.
        """
        response = self.client.get(reverse('pts-package-search'), {
            'package_name': self.binary_package.name
        })

        self.assertRedirects(response, self.source_package.get_absolute_url())

    def test_package_does_not_exist(self):
        """
        Tests the package search when the given package does not exist.
        """
        response = self.client.get(reverse('pts-package-search'), {
            'package_name': 'no-exist'
        })

        self.assertTemplateUsed('core/package_search.html')
        self.assertIn('package_name', response.context)
        self.assertEqual(response.context['package_name'], 'no-exist')


class IndexViewTest(TestCase):
    def test_index(self):
        """
        Tests that the correct template is rendered when the index page is
        accessed.
        """
        response = self.client.get('/')
        self.assertTemplateUsed(response, 'core/index.html')


class PackageAutocompleteViewTest(TestCase):
    def setUp(self):
        SourcePackage.objects.create(name='dummy-package')
        SourcePackage.objects.create(name='d-package')
        SourcePackage.objects.create(name='package')
        PseudoPackage.objects.create(name='pseudo-package')
        PseudoPackage.objects.create(name='zzz')
        Package.subscription_only_packages.create(name='ppp')

    def test_source_package_autocomplete(self):
        """
        Tests the autocomplete functionality when the client asks for source
        packages.
        """
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'package_type': 'source',
            'q': 'd',
        })

        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response), 2)
        self.assertIn('dummy-package', response)
        self.assertIn('d-package', response)

        # No packages given when there are no matching source packages
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'package_type': 'source',
            'q': 'z',
        })
        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response), 0)

    def test_pseudo_package_autocomplete(self):
        """
        Tests the autocomplete functionality when the client asks for pseudo
        packages.
        """
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'package_type': 'pseudo',
            'q': 'p',
        })

        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response), 1)
        self.assertIn('pseudo-package', response)

        # No packages given when there are no matching pseudo packages
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'package_type': 'source',
            'q': '-',
        })
        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response), 0)

    def test_all_packages_autocomplete(self):
        """
        Tests the autocomplete functionality when the client does not specify
        the type of package.
        """
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'q': 'p',
        })

        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response), 2)
        self.assertIn('package', response)
        self.assertIn('pseudo-package', response)

        # No packages given when there are no matching packages
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'q': '-',
        })
        response = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response), 0)

    def test_no_query_given(self):
        """
        Tests the autocomplete when there is no query parameter given.
        """
        response = self.client.get(reverse('pts-api-package-autocomplete'), {
            'package_type': 'source',
        })

        self.assertEqual(response.status_code, 404)

