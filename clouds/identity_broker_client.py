# vim: ts=4 et:

import json
import logging
import os
import sys
import time
import urllib.error

from datetime import datetime
from email.utils import parsedate
from urllib.request import Request, urlopen


class IdentityBrokerClient:
    """Client for identity broker

    Export IDENTITY_BROKER_ENDPOINT to override the default broker endpoint.
    Export IDENTITY_BROKER_API_KEY to specify an API key for the broker.

    See README_BROKER.md for more information and a spec.
    """

    _DEFAULT_ENDPOINT = 'https://aws-access.crute.us/api/account'
    _DEFAULT_ACCOUNT = 'alpine-amis-user'
    _LOGFORMAT = '%(name)s - %(levelname)s - %(message)s'

    def __init__(self, endpoint=None, key=None, account=None, debug=False, not_regions=[]):
        # log to STDOUT so that it's not all red when executed by Packer
        self._logger = logging.getLogger('identity-broker')
        self._logger.setLevel(logging.DEBUG if debug else logging.INFO)
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter(self._LOGFORMAT))
        self._logger.addHandler(console)

        self._endpoint = os.environ.get('IDENTITY_BROKER_ENDPOINT') or endpoint \
            or self._DEFAULT_ENDPOINT
        self._key = os.environ.get('IDENTITY_BROKER_API_KEY') or key
        self._account = account or self._DEFAULT_ACCOUNT
        if not self._key:
            raise Exception('No identity broker key found')
        self._not_regions = not_regions

        self._headers = {
            'Accept': 'application/vnd.broker.v2+json',
            'X-API-Key': self._key
        }
        self._cache = {}
        self._expires = {}
        self._default_region = {}

    def _is_cache_valid(self, path):
        if path not in self._cache:
            return False

        # path is subject to expiry AND its time has passed
        if self._expires[path] and self._expires[path] < datetime.utcnow():
            return False

        return True

    def _get(self, path):
        self._logger.debug("request: %s", path)
        if not self._is_cache_valid(path):
            while True:     # to handle rate limits
                try:
                    res = urlopen(Request(path, headers=self._headers))
                except urllib.error.HTTPError as ex:
                    if ex.status == 401:
                        raise Exception('Expired or invalid identity broker token')

                    if ex.status == 406:
                        raise Exception('Invalid or malformed identity broker token')

                    # TODO: will this be entirely handled by the 401 above?
                    if ex.headers.get('Location') == '/logout':
                        raise Exception('Identity broker token is expired')

                    if ex.status == 429:
                        self._logger.warning(
                            'Rate-limited by identity broker, sleeping 30 seconds')
                        time.sleep(30)
                        continue

                    raise ex

                if res.status not in {200, 429}:
                    raise Exception(res.reason)

                # never expires without valid RFC 1123 Expires header
                if expires := res.getheader('Expires'):
                    expires = parsedate(expires)
                    # convert RFC 1123 to datetime, if parsed successfully
                    expires = datetime(*expires[:6])

                self._expires[path] = expires
                self._cache[path] = json.load(res)
                break

        self._logger.debug("response: %s", self._cache[path])
        return self._cache[path]

    def get_credentials_url(self, vendor):
        accounts = self._get(self._endpoint)
        if vendor not in accounts:
            raise Exception(f'No {vendor} credentials found')

        for account in accounts[vendor]:
            if account['short_name'] == self._account:
                return account['credentials_url']

        raise Exception('No account credentials found')

    def get_regions(self, vendor):
        out = {}

        for region in self._get(self.get_credentials_url(vendor)):
            if region['enabled'] and region['name'] not in self._not_regions:
                out[region['name']] = region['credentials_url']

            if region['default']:
                self._default_region[vendor] = region['name']

        return out

    def get_default_region(self, vendor):
        if vendor not in self._default_region:
            self.get_regions(vendor)

        return self._default_region.get(vendor)

    def get_credentials(self, vendor, region=None):
        if not region:
            region = self.get_default_region(vendor)

        return self._get(self.get_regions(vendor)[region])
